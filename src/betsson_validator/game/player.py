"""Juega como un jugador: mira la pantalla, localiza controles por su aspecto y lee el HUD.

No sabe nada del proveedor: todo lo específico de un juego está en su perfil aprendido
(profiles.py). Si el perfil deja de encajar (botón movido, texto cambiado), se reaprende con la
IA de visión una única vez y queda anotado; si tampoco así se puede, el resultado es FAIL.

Regla de seguridad: un giro nunca se repite. Si no se confirma, se informa, no se reintenta.
"""

import re
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import numpy.typing as npt
from playwright.sync_api import Page

from betsson_validator.casino.betsson import GameHandle
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.perception.hud import HudLabels, HudReading, find_message, read_hud
from betsson_validator.perception.learner import Box, ScreenAnalysis, ScreenLearner
from betsson_validator.perception.motion import (
    SpinLifecycle,
    detect_spin_lifecycle,
    motion_score,
)
from betsson_validator.perception.ocr import TextBox, TextReader
from betsson_validator.perception.templates import crop, find_template
from betsson_validator.profiles import GameProfile

Image = npt.NDArray[np.uint8]
Point = tuple[float, float]

_TEMPLATE_PADDING = 4
_STILL_SCORE = 0.01


class GameError(RuntimeError):
    pass


@dataclass(frozen=True)
class GameTimings:
    ready_timeout_s: float = 150
    learn_after_s: float = 20  # no se llama a la IA mientras el juego aún está cargando
    spin_timeout_s: float = 45
    capture_interval_ms: int = 150
    settle_after_spin_ms: int = 1500
    max_bet_presses: int = 25


@dataclass(frozen=True)
class ScreenObservation:
    hud: HudReading
    evidence: str
    message: str | None


@dataclass(frozen=True)
class SpinObservation:
    lifecycle: SpinLifecycle
    scores: tuple[float, ...]
    evidence: tuple[str, ...]


@dataclass
class ScreenModel:
    """Interpreta capturas: lee el HUD, localiza controles y reaprende el perfil si no encaja."""

    profile: GameProfile
    reader: TextReader
    currency: str
    learner: ScreenLearner | None = None
    notes: list[str] = field(default_factory=list)
    _learned: bool = False

    def labels(self) -> HudLabels:
        return HudLabels(
            credit=self.profile.credit_label, bet=self.profile.bet_label, win=self.profile.win_label
        )

    def read(self, image: Image) -> tuple[HudReading, list[TextBox]]:
        boxes = self.reader.read(image)
        return read_hud(boxes, self.labels(), self.currency), boxes

    def read_or_learn(self, image: Image) -> tuple[HudReading, list[TextBox]]:
        """Si las etiquetas del perfil ya no aparecen (texto cambiado), las reaprende."""
        hud, boxes = self.read(image)
        if (hud.credit is None or hud.bet is None) and self.learn(
            image, "no se encontraron las etiquetas de crédito o apuesta"
        ):
            hud, boxes = self.read(image)
        return hud, boxes

    def locate(self, control: str, image: Image) -> Point | None:
        template = self.profile.template(control)
        if template is None:
            return None
        match = find_template(image, template)
        if match is None:
            return None
        height, width = image.shape[:2]
        center_x, center_y = match.center
        return center_x / width, center_y / height

    def locate_or_learn(self, control: str, image: Image) -> Point:
        point = self.locate(control, image)
        if point is None and self.learn(image, f"no se encontró el control '{control}'"):
            point = self.locate(control, image)
        if point is None:
            raise GameError(f"No se encuentra el control '{control}' en la pantalla del juego.")
        return point

    def learn(self, image: Image, reason: str) -> ScreenAnalysis | None:
        """Reaprende con la IA (una vez por ejecución) y aplica el resultado en memoria."""
        if self.learner is None or self._learned:
            return None
        self._learned = True
        analysis = self.learner.analyze(image)
        self.apply(analysis, image)
        self.notes.append(f"Perfil reaprendido con IA de visión: {reason}.")
        return analysis

    def apply(self, analysis: ScreenAnalysis, image: Image) -> None:
        controls: dict[str, Box | None] = {
            "continue": analysis.continue_button,
            "spin": analysis.spin_button,
            "bet_down": analysis.bet_decrease_button,
        }
        for control, box in controls.items():
            if box is not None:
                x, y, w, h = box.as_tuple()
                p = _TEMPLATE_PADDING
                self.profile.templates[control] = crop(image, (x - p, y - p, w + 2 * p, h + 2 * p))
        if analysis.credit_label:
            self.profile.credit_label = analysis.credit_label
        if analysis.bet_label:
            self.profile.bet_label = analysis.bet_label
        if analysis.win_label:
            self.profile.win_label = analysis.win_label
        if analysis.reels_area is not None:
            height, width = image.shape[:2]
            x, y, w, h = analysis.reels_area.as_tuple()
            self.profile.reels_area = (x / width, y / height, (x + w) / width, (y + h) / height)

    def reels(self, image: Image) -> Image:
        if self.profile.reels_area is None:
            return image
        x1, y1, x2, y2 = self.profile.reels_area
        height, width = image.shape[:2]
        return image[int(height * y1) : int(height * y2), int(width * x1) : int(width * x2)]


@dataclass
class ScreenGame:
    """Actúa sobre el juego: captura, pulsa y observa. La interpretación es del modelo."""

    page: Page
    handle: GameHandle
    model: ScreenModel
    evidence: EvidenceRecorder
    message_pattern: re.Pattern[str]
    dismiss_labels: tuple[str, ...]
    timings: GameTimings = field(default_factory=GameTimings)

    # --- Captura y lectura ---------------------------------------------------------------

    def capture(self) -> Image:
        """Lo que ve el jugador en la zona del juego (incluye lo que se superponga encima)."""
        box = self.handle.iframe.bounding_box()
        if box is None:
            raise GameError("El juego no está visible en la página.")
        png = self.page.screenshot(clip=box, animations="allow")
        image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise GameError("No se pudo capturar la pantalla del juego.")
        return np.asarray(image, dtype=np.uint8)

    def observe(self, name: str) -> ScreenObservation:
        image = self.capture()
        hud, boxes = self.model.read(image)
        return self._observation(name, image, hud, boxes)

    def _observation(
        self, name: str, image: Image, hud: HudReading, boxes: list[TextBox]
    ) -> ScreenObservation:
        path = self.evidence.save_image(name, image)
        message = find_message(boxes, self.message_pattern)
        return ScreenObservation(hud=hud, evidence=str(path), message=message)

    # --- Controles -----------------------------------------------------------------------

    def click(self, point: Point) -> None:
        """Pulsa en un punto relativo (0-1) del juego."""
        box = self.handle.iframe.bounding_box()
        if box is None:
            raise GameError("El juego no está visible en la página.")
        self.page.mouse.click(
            box["x"] + box["width"] * point[0], box["y"] + box["height"] * point[1]
        )

    def wait_until_ready(self) -> ScreenObservation:
        """Espera a ver crédito y apuesta; pasa la pantalla de bienvenida si la hay."""
        start = time.monotonic()
        previous: Image | None = None
        still = 0
        while time.monotonic() - start < self.timings.ready_timeout_s:
            image = self.capture()
            hud, boxes = self.model.read(image)
            if hud.credit is not None and hud.bet is not None:
                return self._observation("juego_listo", image, hud, boxes)
            still = still + 1 if previous is not None and _is_still(previous, image) else 0
            previous = image
            point = self.model.locate("continue", image)
            if point is not None:
                self.click(point)
            elif time.monotonic() - start > self.timings.learn_after_s and still >= 3:  # noqa: PLR2004
                analysis = self.model.learn(image, "no se veía el crédito ni la apuesta")
                if analysis is not None and analysis.continue_button is not None:
                    self.click(self.model.locate("continue", image) or (0.5, 0.5))
            self.page.wait_for_timeout(1000)
        raise GameError("El juego no mostró el crédito y la apuesta a tiempo.")

    def set_minimum_bet(self) -> ScreenObservation:
        """Baja la apuesta hasta que deja de bajar, comprobándolo en pantalla cada vez."""
        image = self.capture()
        hud, _ = self.model.read_or_learn(image)
        current = hud.bet.money.amount if hud.bet else None
        unchanged = 0
        for _ in range(self.timings.max_bet_presses):
            self.click(self.model.locate_or_learn("bet_down", image))
            self.page.wait_for_timeout(350)
            image = self.capture()
            hud, _ = self.model.read(image)
            new = hud.bet.money.amount if hud.bet else None
            unchanged = unchanged + 1 if new is not None and new == current else 0
            current = new if new is not None else current
            if unchanged >= 2:  # noqa: PLR2004 - dos pulsaciones sin cambio: es el mínimo
                break
        return self.observe("apuesta_minima")

    def spin_and_watch(self) -> SpinObservation:
        """Pulsa girar UNA vez y vigila los rodillos hasta que el giro termina (o no empieza)."""
        before = self.capture()
        point = self.model.locate_or_learn("spin", before)
        evidence = [str(self.evidence.save_image("antes_de_girar", before))]
        previous = self.model.reels(before)
        self.click(point)
        scores: list[float] = []
        mid_saved = False
        deadline = time.monotonic() + self.timings.spin_timeout_s
        while time.monotonic() < deadline:
            image = self.capture()
            current = self.model.reels(image)
            scores.append(motion_score(previous, current))
            previous = current
            lifecycle = detect_spin_lifecycle(scores)
            if lifecycle.started and not mid_saved:
                evidence.append(str(self.evidence.save_image("girando", image)))
                mid_saved = True
            if lifecycle.completed:
                break
            self.page.wait_for_timeout(self.timings.capture_interval_ms)
        self.page.wait_for_timeout(self.timings.settle_after_spin_ms)
        return SpinObservation(detect_spin_lifecycle(scores), tuple(scores), tuple(evidence))

    def dismiss_message(self) -> bool:
        """Cierra un diálogo del juego pulsando su botón, localizado por OCR."""
        image = self.capture()
        labels = {label.upper() for label in self.dismiss_labels}
        for box in self.model.reader.read(image):
            if box.text.strip().upper() in labels:
                height, width = image.shape[:2]
                self.click(((box.x + box.width / 2) / width, (box.y + box.height / 2) / height))
                return True
        return False


def _is_still(previous: Image, current: Image) -> bool:
    return previous.shape == current.shape and motion_score(previous, current) < _STILL_SCORE
