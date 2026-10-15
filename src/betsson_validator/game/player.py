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
from playwright.sync_api import Page

from betsson_validator.casino.betsson import GameHandle
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.screen_model import (
    GameError,
    Image,
    Point,
    ScreenModel,
)
from betsson_validator.perception.hud import (
    HudReading,
    find_message,
)
from betsson_validator.perception.motion import (
    MotionThresholds,
    SpinLifecycle,
    adaptive_thresholds,
    detect_spin_lifecycle,
    motion_score,
)
from betsson_validator.perception.ocr import TextBox

_STILL_SCORE = 0.01
_BLANK_SCREEN_STD = 15.0  # desviación de grises por debajo de la cual la pantalla está vacía


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
        seen_win = hud.win is not None
        settled = False
        while not settled and time.monotonic() < deadline:
            self.page.wait_for_timeout(1000)
            next_image = self.capture()
            next_hud, next_boxes = self.model.read(next_image)
            # Un premio que se vio y ya no se lee no es "sin premio": se vuelve a mirar.
            settled = same_reading(hud, next_hud) and not (seen_win and next_hud.win is None)
            seen_win = seen_win or next_hud.win is not None
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
        image = self.capture()
        path = self.evidence.save_image("juego_no_listo", image)
        notice = (
            find_message(self.model.reader.read(image), self.notice_pattern)
            if self.notice_pattern
            else None
        )
        shown = f"; el juego muestra «{notice}»" if notice else ""
        raise GameError(
            f"El juego no mostró el crédito y la apuesta a tiempo{shown} (ver {path.name})."
        )

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
        minimum = self.model.profile.min_bet
        if current is not None and minimum is not None and current <= minimum:
            # Ya está en el mínimo conocido: con el "-" desactivado, buscarlo solo puede
            # encontrar otra cosa (15/10, Big Bass: abrió el panel de tirada automática).
            return self.observe("apuesta_minima")
        unchanged = 0
        spin = self.model.locate("spin", image)
        for _ in range(self.timings.max_bet_presses):
            # Solo junto al botón de girar: un "-" en otro sitio es otra cosa (15/10, Big Bass:
            # un falso "-" abrió el panel de tirada automática).
            point = self.model.locate_near("bet_down", image, spin)
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


def same_reading(a: HudReading, b: HudReading) -> bool:
    """Dos lecturas seguidas del marcador coinciden: el mismo crédito y el mismo premio.

    Un premio que aparece en una lectura y no en la otra NO es estable: puede
    ser una etiqueta que parpadea o una lectura fallida, y un premio desconocido no es cero.
    """
    if a.credit is None or b.credit is None or a.credit.money != b.credit.money:
        return False
    if a.win is None or b.win is None:
        return a.win is None and b.win is None
    return a.win.money == b.win.money


def is_still(previous: Image, current: Image) -> bool:
    """Dos capturas prácticamente iguales (la pantalla no cambia)."""
    return previous.shape == current.shape and motion_score(previous, current) < _STILL_SCORE
