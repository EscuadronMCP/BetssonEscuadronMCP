"""Cuándo se permite pagar a la IA durante la espera del juego (eficiencia, decisión 003)."""

import re
import time
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import pytest

from betsson_validator.game.player import GameTimings, ScreenGame
from betsson_validator.game.screen_model import ScreenModel
from betsson_validator.perception.templates import crop
from betsson_validator.profiles import GameProfile

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pragmaticplay"


def game(loading: list[bool] | None, timings: GameTimings | None = None) -> ScreenGame:
    signal = (lambda: loading[0]) if loading is not None else None
    placeholder = cast(Any, None)  # page, handle, modelo y evidencias no intervienen aquí
    return ScreenGame(
        page=placeholder,
        handle=placeholder,
        model=placeholder,
        evidence=placeholder,
        message_pattern=re.compile("x"),
        dismiss_labels=(),
        timings=timings or GameTimings(),
        loading_finished=signal,
    )


REAL_SCREEN = np.asarray(cv2.imread(str(FIXTURES / "sweet_bonanza_ready.png")), dtype=np.uint8)
BLACK_SCREEN = np.zeros((504, 896, 3), dtype=np.uint8)


def test_never_learns_from_a_blank_screen() -> None:
    long_ago = time.monotonic() - 1000
    assert not game(None)._may_learn(long_ago, BLACK_SCREEN)


def test_waits_for_the_game_to_finish_loading() -> None:
    loading = [False]
    g = game(loading, GameTimings(learn_grace_after_loading_s=0))
    assert not g._may_learn(time.monotonic(), REAL_SCREEN)
    loading[0] = True
    assert g._may_learn(time.monotonic(), REAL_SCREEN)


def test_grace_period_after_loading() -> None:
    g = game([True], GameTimings(learn_grace_after_loading_s=60))
    assert not g._may_learn(time.monotonic(), REAL_SCREEN)


def test_without_loading_signal_uses_elapsed_time() -> None:
    g = game(None, GameTimings(learn_after_s=45))
    assert not g._may_learn(time.monotonic(), REAL_SCREEN)
    assert g._may_learn(time.monotonic() - 50, REAL_SCREEN)


class _NoWaitPage:
    def wait_for_timeout(self, _ms: float) -> None:
        return None


class _ScriptedGame(ScreenGame):
    """Devuelve capturas preparadas en lugar de capturar la página."""

    frames: list[np.ndarray]

    def capture(self) -> np.ndarray:
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]


def test_transient_animation_does_not_pay_for_ai() -> None:
    spin = crop(REAL_SCREEN, (663, 429, 64, 57))
    profile = GameProfile("p", "g", "CRÉDITO", "APUESTA", "", templates={"spin": spin})

    class CountingLearner:
        calls = 0

        @property
        def cost_usd(self) -> float:
            return 0.0

        def analyze(self, image: np.ndarray, *, model: str | None = None) -> Any:
            CountingLearner.calls += 1
            raise AssertionError("no debería llamarse a la IA")

    model = ScreenModel(profile, cast(Any, None), "EUR", CountingLearner())
    game = _ScriptedGame(
        page=cast(Any, _NoWaitPage()),
        handle=cast(Any, None),
        model=model,
        evidence=cast(Any, None),
        message_pattern=re.compile("x"),
        dismiss_labels=(),
        timings=GameTimings(locate_patience_s=60),
    )
    game.frames = [BLACK_SCREEN, BLACK_SCREEN, REAL_SCREEN]
    point, _ = game._locate_patiently("spin")
    assert point == pytest.approx(((663 + 32) / 896, (429 + 28) / 504), abs=0.02)
    assert CountingLearner.calls == 0


def test_spin_is_clicked_exactly_once_even_if_the_game_does_not_react() -> None:
    """Nunca se repite una tirada: sin reacción del juego se informa, no se reintenta."""
    spin = crop(REAL_SCREEN, (663, 429, 64, 57))
    profile = GameProfile("p", "g", "CRÉDITO", "APUESTA", "", templates={"spin": spin})
    model = ScreenModel(profile, cast(Any, None), "EUR", None)

    class Page:
        clicks = 0

        def wait_for_timeout(self, _ms: float) -> None:
            return None

        @property
        def mouse(self) -> Any:
            page = self

            class Mouse:
                def click(self, _x: float, _y: float) -> None:
                    page.clicks += 1

            return Mouse()

    class Handle:
        class iframe:  # noqa: N801 - imita el atributo del manejador real
            @staticmethod
            def bounding_box() -> dict[str, float]:
                return {"x": 0, "y": 0, "width": 896, "height": 504}

    page = Page()
    game = _ScriptedGame(
        page=cast(Any, page),
        handle=cast(Any, Handle()),
        model=model,
        evidence=cast(Any, None),
        message_pattern=re.compile("x"),
        dismiss_labels=(),
        timings=GameTimings(spin_start_timeout_s=0.05, settle_after_spin_ms=0, idle_samples=1),
    )
    game.frames = [REAL_SCREEN]  # la pantalla nunca cambia: el juego no reacciona
    observation = game.spin_and_watch()
    assert page.clicks == 1
    assert not observation.lifecycle.started
