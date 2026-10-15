"""La lectura final del marcador solo vale si crédito y premio dejaron de cambiar (auditoría P2)."""

import re
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import numpy as np

from betsson_validator.domain.checks import Check
from betsson_validator.domain.money import Money
from betsson_validator.domain.verdict import Status
from betsson_validator.game.player import ScreenGame, same_reading
from betsson_validator.perception.hud import AmountReading, HudReading
from betsson_validator.scenarios.evaluation import evaluate_completed_spin
from tests.unit.test_evaluation import WINNING_SPIN, statuses


def reading(amount: str | None) -> AmountReading | None:
    if amount is None:
        return None
    return AmountReading(Money(amount=Decimal(amount), currency="EUR"), amount, 0.99)


def hud(credit: str | None, win: str | None = None) -> HudReading:
    return HudReading(credit=reading(credit), bet=reading("0.20"), win=reading(win), texts=())


def test_same_credit_and_win_is_settled() -> None:
    assert same_reading(hud("64.65", "0.15"), hud("64.65", "0.15"))


def test_a_prize_that_disappears_is_not_stable() -> None:
    """Auditoría R03-03: un premio que deja de leerse no es "sin premio"."""
    assert not same_reading(hud("64.65", "0.15"), hud("64.65", None))
    assert same_reading(hud("64.65"), hud("64.65"))  # pérdida legítima: nunca hubo premio


def test_a_win_counter_still_going_up_is_not_settled() -> None:
    assert not same_reading(hud("64.65", "0.10"), hud("64.65", "0.15"))


def test_credit_must_be_read_and_equal() -> None:
    assert not same_reading(hud("64.50"), hud("64.65"))
    assert not same_reading(hud(None), hud(None))


class _Page:
    def wait_for_timeout(self, _ms: float) -> None:
        return None


class _Evidence:
    def save_image(self, name: str, _image: object) -> Path:
        return Path(f"{name}.jpg")


class _Model:
    def __init__(self, readings: list[HudReading]) -> None:
        self.readings = readings

    def read(self, _image: object) -> tuple[HudReading, list[object]]:
        return (self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]), []


class _Game(ScreenGame):
    def capture(self) -> np.ndarray:
        return np.zeros((10, 10, 3), dtype=np.uint8)


def observe(readings: list[HudReading], timeout_s: float) -> Any:
    game = _Game(
        page=cast(Any, _Page()),
        handle=cast(Any, None),
        model=cast(Any, _Model(readings)),
        evidence=cast(Any, _Evidence()),
        message_pattern=re.compile("fondos insuficientes"),
        dismiss_labels=(),
    )
    return game.observe_settled("despues_de_girar", timeout_s=timeout_s)


def test_waits_until_the_win_counter_stops() -> None:
    result = observe([hud("64.50", "0.05"), hud("64.55", "0.10"), hud("64.65", "0.15")], 5)
    assert result.settled
    assert result.hud.credit.money.amount == Decimal("64.65")


class _EverChangingModel:
    """Un contador que nunca se detiene dentro del tiempo de espera."""

    def __init__(self) -> None:
        self.cents = 0

    def read(self, _image: object) -> tuple[HudReading, list[object]]:
        self.cents += 1
        return hud(f"64.{self.cents % 100:02d}"), []


def test_a_reading_that_never_settles_is_flagged() -> None:
    game = _Game(
        page=cast(Any, _Page()),
        handle=cast(Any, None),
        model=cast(Any, _EverChangingModel()),
        evidence=cast(Any, _Evidence()),
        message_pattern=re.compile("fondos insuficientes"),
        dismiss_labels=(),
    )
    assert not game.observe_settled("despues_de_girar", timeout_s=0.05).settled


def test_an_unsettled_final_reading_cannot_prove_the_balance() -> None:
    unsettled = replace(
        WINNING_SPIN, screen_after=replace(WINNING_SPIN.screen_after, settled=False)
    )
    result = {r.check: r for r in evaluate_completed_spin(unsettled)}
    check = result[Check.GAME_BALANCE_CONSISTENT.value]
    assert check.status is Status.FAIL
    assert "no se estabilizó" in str(check.testimonies)
    assert statuses(evaluate_completed_spin(WINNING_SPIN))[check.check] is Status.PASS


def test_blinking_prize_is_observed_again_before_finalizing() -> None:
    """Auditoría R03-03: crédito fijo y premios 1 → None → 2 → 2 terminan en 2, no en None."""
    readings = [
        hud("64.65", "1.00"),
        hud("64.65", None),
        hud("64.65", "2.00"),
        hud("64.65", "2.00"),
    ]
    result = observe(readings, 5)
    assert result.settled
    assert result.hud.win.money.amount == Decimal("2.00")


def test_a_prize_that_never_comes_back_is_not_settled() -> None:
    result = observe([hud("64.65", "1.00"), hud("64.65", None)], 0.05)
    assert not result.settled
