"""Control del juego de Pragmatic Play desde lo que ve el jugador (capturas, OCR, movimiento)."""

import time
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt
from playwright.sync_api import Page

from betsson_validator.casino.betsson import GameHandle
from betsson_validator.config.provider import Point, ScreenProfile
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.perception.hud import HudLabels, HudReading, find_message, read_hud
from betsson_validator.perception.motion import SpinLifecycle, detect_spin_lifecycle, motion_score
from betsson_validator.perception.ocr import TextBox, TextReader

Image = npt.NDArray[np.uint8]

_CAPTURE_INTERVAL_MS = 150
_SETTLE_AFTER_SPIN_MS = 1500
_CONTINUE_RETRY_S = 12


class GameError(RuntimeError):
    pass


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


class PragmaticGame:
    def __init__(
        self,
        page: Page,
        handle: GameHandle,
        *,
        profile: ScreenProfile,
        reader: TextReader,
        evidence: EvidenceRecorder,
        currency: str,
    ) -> None:
        self._page = page
        self._handle = handle
        self._profile = profile
        self._reader = reader
        self._evidence = evidence
        self._currency = currency
        self._labels = HudLabels(
            credit=profile.labels.credit, bet=profile.labels.bet, win=profile.labels.win
        )

    def capture(self) -> Image:
        png = self._handle.iframe.screenshot(animations="allow")
        image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise GameError("No se pudo capturar la pantalla del juego.")
        return np.asarray(image, dtype=np.uint8)

    def _click(self, point: Point) -> None:
        box = self._handle.iframe.bounding_box()
        if box is None:
            raise GameError("El juego no está visible en la página.")
        self._page.mouse.click(
            box["x"] + box["width"] * point[0], box["y"] + box["height"] * point[1]
        )

    def _read(self, image: Image) -> tuple[HudReading, list[TextBox]]:
        boxes = self._reader.read(image)
        return read_hud(boxes, self._labels, self._currency), boxes

    def wait_until_ready(self) -> ScreenObservation:
        """Espera a que el jugador vea el HUD; pulsa 'continuar' si sigue la pantalla de inicio."""
        deadline = time.monotonic() + self._profile.ready_timeout_s
        last_continue = time.monotonic()
        while time.monotonic() < deadline:
            image = self.capture()
            hud, boxes = self._read(image)
            if hud.credit is not None and hud.bet is not None:
                return self._observation("juego_listo", image, hud, boxes)
            if time.monotonic() - last_continue > _CONTINUE_RETRY_S:
                self._click(self._profile.controls.continue_)
                last_continue = time.monotonic()
            self._page.wait_for_timeout(1000)
        raise GameError("El juego no mostró el crédito y la apuesta a tiempo.")

    def observe(self, name: str) -> ScreenObservation:
        image = self.capture()
        hud, boxes = self._read(image)
        return self._observation(name, image, hud, boxes)

    def _observation(
        self, name: str, image: Image, hud: HudReading, boxes: list[TextBox]
    ) -> ScreenObservation:
        path = self._evidence.save_image(name, image)
        message = find_message(boxes, self._profile.insufficient_funds_regex)
        return ScreenObservation(hud=hud, evidence=str(path), message=message)

    def set_minimum_bet(self) -> ScreenObservation:
        for _ in range(self._profile.bet_down_presses):
            self._click(self._profile.controls.bet_down)
            self._page.wait_for_timeout(250)
        self._page.wait_for_timeout(800)
        return self.observe("apuesta_minima")

    def spin_and_watch(self) -> SpinObservation:
        """Pulsa girar y vigila la zona de los rodillos hasta que el giro termina (o no empieza)."""
        baseline = self._reels(self.capture())
        before_path = self._evidence.save_image("antes_de_girar", self.capture())
        self._click(self._profile.controls.spin)
        scores: list[float] = []
        previous = baseline
        evidence = [str(before_path)]
        mid_saved = False
        deadline = time.monotonic() + self._profile.spin_timeout_s
        while time.monotonic() < deadline:
            image = self.capture()
            current = self._reels(image)
            scores.append(motion_score(previous, current))
            previous = current
            lifecycle = detect_spin_lifecycle(scores)
            if lifecycle.started and not mid_saved:
                evidence.append(str(self._evidence.save_image("girando", image)))
                mid_saved = True
            if lifecycle.completed:
                break
            self._page.wait_for_timeout(_CAPTURE_INTERVAL_MS)
        self._page.wait_for_timeout(_SETTLE_AFTER_SPIN_MS)
        return SpinObservation(
            lifecycle=detect_spin_lifecycle(scores), scores=tuple(scores), evidence=tuple(evidence)
        )

    def _reels(self, image: Image) -> Image:
        x1, y1, x2, y2 = self._profile.reels_region
        height, width = image.shape[:2]
        return image[int(height * y1) : int(height * y2), int(width * x1) : int(width * x2)]

    def dismiss_message(self) -> bool:
        """Cierra el diálogo del juego pulsando su botón, localizado por OCR como un jugador."""
        image = self.capture()
        label = self._profile.message_dismiss_label.upper()
        for box in self._reader.read(image):
            if box.text.strip().upper() == label:
                height, width = image.shape[:2]
                self._click(((box.x + box.width / 2) / width, (box.y + box.height / 2) / height))
                return True
        return False
