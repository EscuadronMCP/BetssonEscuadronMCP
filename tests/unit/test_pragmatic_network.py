"""Tests con el tráfico real de una tirada en Sweet Bonanza 2500 (15/10), recortado y sin tokens."""

from decimal import Decimal

import pytest

from betsson_validator.providers.pragmatic.network import (
    GameServiceCall,
    NoSpinObservedError,
    balance_from_init,
    redact,
    summarize_round,
)

INIT = GameServiceCall.from_bodies(
    "action=doInit&symbol=vs20swbon2500_cv114&index=1&counter=1",
    "balance=64.70&balance_cash=64.70&c=0.10&l=20&na=s&defc=0.10",
)
SPIN_WITH_TUMBLE = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0&index=2&counter=3",
    "balance=64.50&c=0.01&l=20&tw=0.15&w=0.15&na=s&rs_p=0&rs_c=1",
)
TUMBLE_CONTINUATION = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0&index=3&counter=5",
    "balance=64.50&c=0.01&l=20&tw=0.15&w=0.00&na=c&rs_win=0.00",
)
COLLECT = GameServiceCall.from_bodies(
    "action=doCollect&index=4&counter=7", "balance=64.65&balance_cash=64.65&na=s"
)
LOSING_SPIN = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0", "balance=64.50&c=0.01&l=20&tw=0.00&w=0.00&na=s"
)


def test_real_winning_round_with_tumble_reconciles() -> None:
    calls = [INIT, SPIN_WITH_TUMBLE, TUMBLE_CONTINUATION, COLLECT]
    spin = summarize_round(calls, balance_from_init(calls[:1]) or Decimal(0))
    assert spin.wager == Decimal("0.20")
    assert spin.balance_before == Decimal("64.70")
    assert spin.balance_after == Decimal("64.65")
    assert spin.total_win == Decimal("0.15")
    assert spin.payout == Decimal("0.15")
    assert spin.settled
    assert spin.calls == 3


def test_round_is_not_settled_until_collect() -> None:
    spin = summarize_round([INIT, SPIN_WITH_TUMBLE, TUMBLE_CONTINUATION], Decimal("64.70"))
    assert not spin.settled


def test_first_tumble_response_is_not_settled_even_with_na_s() -> None:
    assert not summarize_round([SPIN_WITH_TUMBLE], Decimal("64.70")).settled


def test_losing_spin_is_settled_immediately() -> None:
    spin = summarize_round([INIT, LOSING_SPIN], Decimal("64.70"))
    assert spin.settled
    assert spin.payout == Decimal("0.00")
    assert spin.total_win == Decimal("0.00")


def test_no_spin_is_reported() -> None:
    with pytest.raises(NoSpinObservedError):
        summarize_round([INIT], Decimal("64.70"))


def test_redact_hides_session_tokens() -> None:
    raw = "action=doInit&mgckey=AUTHTOKEN@9a96~stylename@btsn~SESSION@1d10-ab&token=62a9"
    clean = redact(raw)
    assert "9a96" not in clean
    assert "1d10" not in clean
    assert "62a9" not in clean
    assert "action=doInit" in clean
