"""Cuándo se permite pagar a la IA durante la espera del juego (eficiencia, decisión 003)."""

import re
import time
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from betsson_validator.game.player import GameTimings, ScreenGame

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
