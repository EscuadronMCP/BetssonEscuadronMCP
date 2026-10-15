"""Eventos postMessage reales de Sweet Bonanza 2500 en betsson.es (15/10), recortados."""

from dataclasses import replace
from decimal import Decimal
from typing import Any

from betsson_validator.domain.checks import Check
from betsson_validator.domain.verdict import Outcome, Status
from betsson_validator.providers.pragmatic.events import loading_finished, summarize_events
from betsson_validator.scenarios.evaluation import (
    EVENTS,
    evaluate_completed_spin,
    evaluate_insufficient_balance,
)
from tests.unit.test_evaluation import REJECTED_SPIN, WINNING_SPIN

COMMON: dict[str, Any] = {
    "sender": "vs20swbon2500_cv114",
    "lang": "ES",
    "success": True,
    "betAmount": 0.2,
}
# Tirada real con cascadas: 198,25 - 0,20 + 1,50 = 199,55
WINNING_ROUND: list[dict[str, Any]] = [
    {
        **COMMON,
        "winAmount": 0,
        "balanceBefore": 198.25,
        "balanceAfter": 198.25,
        "name": "gameRoundStart",
    },
    {
        **COMMON,
        "winAmount": 0,
        "balanceBefore": 198.25,
        "balanceAfter": 198.25,
        "name": "gameRoundStarted",
    },
    {
        **COMMON,
        "winAmount": 0,
        "balanceBefore": 198.25,
        "balanceAfter": 198.25,
        "name": "spinStarted",
    },
    {"event": "visualBalanceUpdate", "params": {"currency": "€", "newAmount": 198.05, "win": 0.05}},
    {
        **COMMON,
        "winAmount": 0.21,
        "balanceBefore": 198.05,
        "balanceAfter": 198.05,
        "name": "spinEnded",
    },
    {
        **COMMON,
        "winAmount": 1.5,
        "balanceBefore": 199.55,
        "balanceAfter": 199.55,
        "name": "gameRoundEnded",
    },
]
# Cuenta sin saldo real
REJECTED: list[dict[str, Any]] = [
    {"event": "betChanged", "params": {"bet": 0.2}},
    {**COMMON, "winAmount": 0, "balanceBefore": 0, "balanceAfter": 0, "name": "balanceTooLow"},
    {"event": "updateBalance", "params": {"total": {"currency": "€", "amount": 0}}, "lang": "ES"},
]


def test_winning_round_is_summarized() -> None:
    summary = summarize_events(WINNING_ROUND)
    assert summary.round_started and summary.round_ended
    assert summary.bet == Decimal("0.2")
    assert summary.win == Decimal("1.5")
    assert summary.balance_before == Decimal("198.25")
    assert summary.balance_after == Decimal("199.55")
    assert summary.languages == ("es",)
    assert summary.currencies == ("EUR",)
    assert not summary.low_balance


def test_rejected_spin_is_summarized() -> None:
    summary = summarize_events(REJECTED)
    assert summary.low_balance
    assert not summary.round_started
    assert summary.currencies == ("EUR",)


def test_no_events_is_unavailable_not_a_failure() -> None:
    summary = summarize_events([])
    assert not summary.received
    results = evaluate_completed_spin(replace(WINNING_SPIN, events=summary))
    for result in results:
        events = [t for t in result.testimonies if t.witness == EVENTS]
        assert events and events[0].outcome is Outcome.UNAVAILABLE


def test_events_contradicting_the_screen_are_a_discrepancy() -> None:
    # La pantalla dice 64,65 tras la tirada; el juego comunica otro saldo final.
    events = summarize_events(
        [
            {**COMMON, "winAmount": 0.15, "balanceBefore": 64.7, "name": "gameRoundStarted"},
            {**COMMON, "winAmount": 0.15, "balanceAfter": 64.60, "name": "gameRoundEnded"},
        ]
    )
    results = {r.check: r for r in evaluate_completed_spin(replace(WINNING_SPIN, events=events))}
    check = results[Check.GAME_BALANCE_CONSISTENT.value]
    assert check.status is Status.FAIL
    assert "Discrepancia" in check.reason and EVENTS in check.reason


def test_rejection_confirmed_by_events() -> None:
    results = evaluate_insufficient_balance(
        replace(REJECTED_SPIN, events=summarize_events(REJECTED))
    )
    assert {r.status for r in results} == {Status.PASS}


def test_round_started_contradicts_rejection() -> None:
    events = summarize_events(WINNING_ROUND)
    results = {
        r.check: r for r in evaluate_insufficient_balance(replace(REJECTED_SPIN, events=events))
    }
    assert results[Check.SPIN_REJECTED.value].status is Status.FAIL


def test_wrong_language_is_reported() -> None:
    english = summarize_events([{**COMMON, "lang": "EN", "name": "balanceTooLow"}])
    results = {
        r.check: r for r in evaluate_insufficient_balance(replace(REJECTED_SPIN, events=english))
    }
    assert results[Check.INSUFFICIENT_MESSAGE_SHOWN.value].status is Status.FAIL


def test_loading_finished_only_after_the_game_says_so() -> None:

    assert not loading_finished([{"name": "loadingProgress"}, {"name": "gameLoadingStarted"}])
    assert loading_finished([{"name": "gameLoadingStarted"}, {"name": "gameLoadingEnded"}])
