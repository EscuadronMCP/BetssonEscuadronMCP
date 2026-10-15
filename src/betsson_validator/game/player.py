"""Juega como un jugador: mira la pantalla, localiza controles por su aspecto y lee el HUD.

No sabe nada del proveedor: todo lo específico de un juego está en su perfil aprendido
(profiles.py). Si el perfil deja de encajar (botón movido, texto cambiado), se reaprende con la
IA de visión una única vez y queda anotado; si tampoco así se puede, el resultado es FAIL.

Regla de seguridad: un giro nunca se repite. Si no se confirma, se informa, no se reintenta.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import cv2
import numpy as np
import numpy.typing as npt
from playwright.sync_api import Page

from betsson_validator.casino.betsson import GameHandle
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.perception.hud import (
    HudLabels,
    HudReading,
    find_amount,
    find_message,
    read_hud,
)
from betsson_validator.perception.learner import Box, ScreenAnalysis, ScreenLearner
from betsson_validator.perception.motion import (
    MotionThresholds,
    SpinLifecycle,
    adaptive_thresholds,
    detect_spin_lifecycle,
    motion_score,
)
from betsson_validator.perception.ocr import TextBox, TextReader
from betsson_validator.perception.templates import TemplateMatch, crop, find_template
from betsson_validator.profiles import GameProfile

Image = npt.NDArray[np.uint8]
Point = tuple[float, float]

_TEMPLATE_INNER = 0.7  # fracción central del control que se guarda como plantilla
_STILL_SCORE = 0.01
_BLANK_SCREEN_STD = 15.0  # desviación de grises por debajo de la cual la pantalla está vacía


class GameError(RuntimeError):
    pass


@dataclass(frozen=True)
class GameTimings:
    ready_timeout_s: float = 150
    # Sin señal de fin de carga, no se llama a la IA antes de esto: una carga lenta deja la
    # pantalla quieta y parecería un cambio de interfaz (llamada inútil).
    learn_after_s: float = 45
    learn_grace_after_loading_s: float = 10
    spin_timeout_s: float = 45
    spin_start_timeout_s: float = 8
    idle_samples: int = 6  # capturas para medir la actividad de fondo antes de girar
    locate_patience_s: float = 4  # reintentos locales antes de pagar a la IA por un control
    capture_interval_ms: int = 150
    settle_after_spin_ms: int = 1500
    max_bet_presses: int = 25


@dataclass(frozen=True)
class ScreenObservation:
    hud: HudReading
    evidence: str
    message: str | None
    # Cualquier otro aviso del juego (p. ej. "Sesión expirada"): explica un fallo, nunca lo oculta.
    notice: str | None = None
    # False si el marcador seguía cambiando al agotarse la espera: la lectura no vale como prueba.
    settled: bool = True


@dataclass(frozen=True)
class SpinObservation:
    lifecycle: SpinLifecycle
    scores: tuple[float, ...]
    evidence: tuple[str, ...]
    thresholds: MotionThresholds | None = None


@dataclass
class ScreenModel:
    """Interpreta capturas: lee el HUD, localiza controles y reaprende el perfil si no encaja."""

    profile: GameProfile
    reader: TextReader
    currency: str
    learner: ScreenLearner | None = None
    # Etiquetas de premio habituales en el idioma del mercado: el premio solo aparece cuando hay
    # ganancia, así que no siempre se puede aprender de la pantalla de juego.
    win_candidates: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)
    _learned: bool = False

    def labels(self) -> HudLabels:
        return HudLabels(
            credit=self.profile.credit_label, bet=self.profile.bet_label, win=self.profile.win_label
        )

    def read(self, image: Image) -> tuple[HudReading, list[TextBox]]:
        boxes = self.reader.read(image)
        height, width = image.shape[:2]
        anchors = {
            name: (rx * width, ry * height) for name, (rx, ry) in self.profile.hud_positions.items()
        }
        hud = read_hud(boxes, self.labels(), self.currency, anchors)
        if hud.win is None and not self.profile.win_label:
            for candidate in self.win_candidates:
                win = find_amount(
                    boxes,
                    candidate,
                    self.currency,
                    anchors.get("win"),
                    (self.profile.credit_label, self.profile.bet_label),
                )
                if win is not None:
                    return replace(hud, win=win), boxes
        return hud, boxes

    def locate(self, control: str, image: Image) -> Point | None:
        """Busca el control por su aspecto. Si otro control del perfil encaja igual o mejor en ese
        mismo sitio (p. ej. '+' cuando '-' está desactivado, o 'girar' en lugar de 'continuar'), la
        localización es ambigua y se rechaza: pulsar el control equivocado puede costar dinero."""
        template = self.profile.template(control)
        if template is None:
            return None
        match = find_template(image, template)
        if match is None:
            return None
        for other, other_template in self.profile.templates.items():
            if other == control:
                continue
            rival = find_template(image, other_template)
            if rival is not None and rival.score >= match.score and _overlap(match, rival):
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
        self.notes.append(
            f"Perfil reaprendido con IA de visión ({self.learner.cost_usd:.4f} $): {reason}."
        )
        return analysis

    def apply(self, analysis: ScreenAnalysis, image: Image) -> None:
        controls: dict[str, Box | None] = {
            "continue": analysis.continue_button,
            "spin": analysis.spin_button,
            "bet_down": analysis.bet_decrease_button,
            "bet_up": analysis.bet_increase_button,
        }
        for control, box in controls.items():
            if box is not None:
                self.profile.templates[control] = control_template(image, box.as_tuple())
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

    def remember_hud_positions(self, hud: HudReading, image: Image) -> None:
        """Guarda dónde se leyeron crédito y apuesta (solo con lecturas ya validadas)."""
        height, width = image.shape[:2]
        for name, reading in (("credit", hud.credit), ("bet", hud.bet), ("win", hud.win)):
            if reading is not None:
                self.profile.hud_positions[name] = (reading.x / width, reading.y / height)

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
    # Señal del propio juego de que terminó de cargar (eventos postMessage), si el proveedor la da.
    loading_finished: Callable[[], bool] | None = None
    notice_pattern: re.Pattern[str] | None = None
    _loaded_at: float | None = field(default=None, init=False)

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

    def observe_settled(self, name: str, timeout_s: float = 12) -> ScreenObservation:
        """Lee el HUD cuando crédito y premio dejan de cambiar (el juego anima sus contadores).

        Si siguen cambiando al agotarse la espera, la observación queda marcada como no
        estabilizada y la evaluación no la acepta como prueba.
        """
        deadline = time.monotonic() + timeout_s
        image = self.capture()
        hud, boxes = self.model.read(image)
        settled = False
        while not settled and time.monotonic() < deadline:
            self.page.wait_for_timeout(1000)
            next_image = self.capture()
            next_hud, next_boxes = self.model.read(next_image)
            settled = same_reading(hud, next_hud)
            image, hud, boxes = next_image, next_hud, next_boxes
        return replace(self._observation(name, image, hud, boxes), settled=settled)

    def _observation(
        self,
        name: str,
        image: Image,
        hud: HudReading,
        boxes: list[TextBox],
        *,
        save: bool = True,
    ) -> ScreenObservation:
        """Lectura de pantalla; solo se guarda como evidencia si sostiene una comprobación."""
        path = str(self.evidence.save_image(name, image)) if save else ""
        message = find_message(boxes, self.message_pattern)
        notice = find_message(boxes, self.notice_pattern) if self.notice_pattern else None
        return ScreenObservation(hud=hud, evidence=path, message=message, notice=notice)

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
                return self._observation("juego_listo", image, hud, boxes, save=False)
            still = still + 1 if previous is not None and is_still(previous, image) else 0
            previous = image
            point = self.model.locate("continue", image)
            if point is not None:
                self.click(point)
            elif self._may_learn(start, image) and still >= 3:  # noqa: PLR2004
                analysis = self.model.learn(image, "no se veía el crédito ni la apuesta")
                found = self.model.locate("continue", image) if analysis is not None else None
                if found is not None:  # nunca un clic a ciegas: podría caer en otro control
                    self.click(found)
            self.page.wait_for_timeout(1000)
        path = self.evidence.save_image("juego_no_listo", self.capture())
        raise GameError(f"El juego no mostró el crédito y la apuesta a tiempo (ver {path.name}).")

    def _locate_patiently(self, control: str) -> tuple[Point, Image]:
        """Localiza un control dando tiempo a que acaben las animaciones de la interfaz.

        Un panel que se cierra o un destello pueden ocultarlo un instante: eso no es un cambio
        de interfaz y no justifica pagar a la IA. Solo si sigue sin aparecer se reaprende.
        """
        deadline = time.monotonic() + self.timings.locate_patience_s
        image = self.capture()
        while True:
            point = self.model.locate(control, image)
            if point is not None:
                return point, image
            if time.monotonic() > deadline:
                return self.model.locate_or_learn(control, image), image
            self.page.wait_for_timeout(500)
            image = self.capture()

    def _may_learn(self, start: float, image: Image) -> bool:
        """Solo se paga a la IA cuando el juego ya cargó y aun así no se reconoce la pantalla.

        El juego avisa del fin de carga un poco antes de pintar su pantalla, así que se deja un
        margen; y una pantalla casi vacía (negra o de un color) no tiene nada que aprender.
        """
        if float(np.std(image)) < _BLANK_SCREEN_STD:
            return False
        now = time.monotonic()
        if self.loading_finished is None:
            return now - start > self.timings.learn_after_s
        if self._loaded_at is None:
            if not self.loading_finished():
                return False
            self._loaded_at = now
        return now - self._loaded_at >= self.timings.learn_grace_after_loading_s

    def set_minimum_bet(self, ready: ScreenObservation) -> ScreenObservation:
        """Baja la apuesta hasta que deja de bajar, comprobándolo en pantalla cada vez.

        Parte de la lectura ya validada del juego listo (no se relee: una lectura pasajera
        fallida no debe costar una llamada a la IA). Si el botón de bajar no está disponible
        (en el mínimo el juego lo desactiva) se deja de pulsar SIN llamar a la IA. El tope
        `max_bet` del llamador sigue impidiendo girar con una apuesta alta.
        """
        image = self.capture()
        current = ready.hud.bet.money.amount if ready.hud.bet else None
        unchanged = 0
        for _ in range(self.timings.max_bet_presses):
            point = self.model.locate("bet_down", image)
            if point is None:
                break
            self.click(point)
            self.page.wait_for_timeout(350)
            image = self.capture()
            hud, _ = self.model.read(image)
            new = hud.bet.money.amount if hud.bet else None
            if new is not None and current is not None and new > current:
                raise GameError(f"Pulsar 'bajar apuesta' la subió ({current} → {new}). No se gira.")
            unchanged = unchanged + 1 if new is not None and new == current else 0
            current = new if new is not None else current
            if unchanged >= 2:  # noqa: PLR2004 - dos pulsaciones sin cambio: es el mínimo
                break
        return self.observe("apuesta_minima")

    def spin_and_watch(self) -> SpinObservation:
        """Pulsa girar UNA vez y vigila los rodillos hasta que el giro termina (o no empieza)."""
        point, before = self._locate_patiently("spin")
        evidence: list[str] = []
        previous, thresholds = self._idle_baseline(before)
        self.click(point)
        scores: list[float] = []
        mid_saved = False
        clicked = time.monotonic()
        deadline = clicked + self.timings.spin_timeout_s
        while time.monotonic() < deadline:
            no_reaction = not detect_spin_lifecycle(scores, thresholds).started
            if no_reaction and time.monotonic() - clicked > self.timings.spin_start_timeout_s:
                break  # un giro real arranca en <1 s: si no, el juego no giró (p. ej. sin saldo)
            image = self.capture()
            current = self.model.reels(image)
            scores.append(motion_score(previous, current))
            previous = current
            lifecycle = detect_spin_lifecycle(scores, thresholds)
            if lifecycle.started and not mid_saved:
                evidence.append(str(self.evidence.save_image("girando", image)))
                mid_saved = True
            if lifecycle.completed:
                break
            self.page.wait_for_timeout(self.timings.capture_interval_ms)
        self.page.wait_for_timeout(self.timings.settle_after_spin_ms)
        return SpinObservation(
            detect_spin_lifecycle(scores, thresholds), tuple(scores), tuple(evidence), thresholds
        )

    def _idle_baseline(self, first: Image) -> tuple[Image, MotionThresholds]:
        """Mide la actividad de fondo antes de girar (animaciones del juego en reposo)."""
        previous = self.model.reels(first)
        idle: list[float] = []
        for _ in range(self.timings.idle_samples):
            self.page.wait_for_timeout(self.timings.capture_interval_ms)
            current = self.model.reels(self.capture())
            idle.append(motion_score(previous, current))
            previous = current
        return previous, adaptive_thresholds(idle)

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


def control_template(image: Image, box: tuple[int, int, int, int]) -> Image:
    """Imagen de un control para reencontrarlo: solo su interior, sin el fondo del juego.

    El fondo cambia entre sesiones (animaciones, paneles) y con él la coincidencia bajaba de
    0,97 a 0,72; con el interior del botón se mantiene por encima de 0,9 (medido en capturas
    reales de sesiones distintas).
    """
    x, y, w, h = box
    dx, dy = round(w * (1 - _TEMPLATE_INNER) / 2), round(h * (1 - _TEMPLATE_INNER) / 2)
    return crop(image, (x + dx, y + dy, w - 2 * dx, h - 2 * dy))


def _overlap(a: TemplateMatch, b: TemplateMatch) -> bool:
    (ax, ay), (bx, by) = a.center, b.center
    return abs(ax - bx) < max(a.width, b.width) / 2 and abs(ay - by) < max(a.height, b.height) / 2


def same_reading(a: HudReading, b: HudReading) -> bool:
    """Dos lecturas seguidas del marcador coinciden: el crédito igual y el premio sin cambiar.

    Un premio que aparece en una lectura y no en la otra se tolera (algunas etiquetas
    parpadean); un premio con dos importes distintos significa que el contador sigue subiendo.
    """
    if a.credit is None or b.credit is None or a.credit.money != b.credit.money:
        return False
    return a.win is None or b.win is None or a.win.money == b.win.money


def is_still(previous: Image, current: Image) -> bool:
    """Dos capturas prácticamente iguales (la pantalla no cambia)."""
    return previous.shape == current.shape and motion_score(previous, current) < _STILL_SCORE
