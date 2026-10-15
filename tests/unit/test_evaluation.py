"""Evaluación de escenarios con los valores reales observados el 15/10 en betsson.es."""

from dataclasses import replace
from decimal import Decimal

from betsson_validator.domain.checks import Check
from betsson_validator.domain.money import Money
from betsson_validator.domain.verdict import CheckResult, Status
from betsson_validator.scenarios.evaluation import (
    evaluate_completed_spin,
    evaluate_insufficient_balance,
)
from betsson_validator.scenarios.evidence import (
    GameEventsSummary,
    MotionSummary,
    NetworkSummary,
    RunEvidence,
    ScreenSnapshot,
)


def eur(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="EUR")


def screen(
    credit: str, bet: str, win: str | None = None, message: str | None = None
) -> ScreenSnapshot:
    return ScreenSnapshot(
        credit=eur(credit),
        bet=eur(bet),
        win=eur(win) if win else None,
        currencies_seen=("EUR",),
        message=message,
        evidence="captura.png",
    )


# Tirada real: 64,70 € - 0,20 € + 0,15 € = 64,65 €
WINNING_SPIN = RunEvidence(
    market_currency="EUR",
    betsson_before=eur("64.70"),
    betsson_after=eur("64.65"),
    betsson_evidence=("cabecera.png",),
    screen_before=screen("64.70", "0.20"),
    screen_after=screen("64.65", "0.20", win="0.15"),
    motion=MotionSummary(started=True, completed=True, samples=23, peak=0.40),
    network=None,
)
SERVER = NetworkSummary(
    spin_requested=True,
    settled=True,
    wager_requested=Decimal("0.20"),
    wager_accepted=Decimal("0.20"),
    declared_win=Decimal("0.15"),
    balance_before=Decimal("64.70"),
    balance_after=Decimal("64.65"),
)
WINNING_SPIN = replace(WINNING_SPIN, network=SERVER)

# Cuenta sin saldo real: mensaje del juego y nada cambia
REJECTED_SPIN = RunEvidence(
    market_currency="EUR",
    betsson_before=eur("0.00"),
    betsson_after=eur("0.00"),
    betsson_evidence=("cabecera.png",),
    screen_before=screen("0.00", "0.20"),
    screen_after=screen("0.00", "0.20", message="Fondos insuficientes para realizar esta"),
    motion=MotionSummary(started=False, completed=False, samples=10, peak=0.02),
    network=NetworkSummary(spin_requested=False),
)


def statuses(results: tuple[CheckResult, ...]) -> dict[str, Status]:
    return {r.check: r.status for r in results}


def test_real_winning_spin_passes_every_check() -> None:
    results = evaluate_completed_spin(WINNING_SPIN)
    assert set(statuses(results).values()) == {Status.PASS}
    assert len(results) == 5


def test_losing_spin_without_win_label_reconciles() -> None:
    losing = replace(
        WINNING_SPIN,
        betsson_after=eur("64.50"),
        screen_after=screen("64.50", "0.20"),
        network=replace(SERVER, balance_after=Decimal("64.50"), declared_win=Decimal("0")),
    )
    assert set(statuses(evaluate_completed_spin(losing)).values()) == {Status.PASS}


def test_betsson_balance_mismatch_is_a_discrepancy() -> None:
    wrong = replace(WINNING_SPIN, betsson_after=eur("64.50"))
    result = statuses(evaluate_completed_spin(wrong))
    assert result[Check.BETSSON_BALANCE_RECONCILES.value] is Status.FAIL


def test_server_disagreeing_with_screen_fails_game_balance() -> None:
    wrong = replace(WINNING_SPIN, network=replace(SERVER, balance_after=Decimal("60")))
    result = {r.check: r for r in evaluate_completed_spin(wrong)}
    check = result[Check.GAME_BALANCE_CONSISTENT.value]
    assert check.status is Status.FAIL
    assert "Discrepancia" in check.reason


def test_click_without_reaction_is_not_a_completed_spin() -> None:
    frozen = replace(WINNING_SPIN, motion=MotionSummary(False, False, 40, 0.0))
    assert statuses(evaluate_completed_spin(frozen))[Check.SPIN_COMPLETED.value] is Status.FAIL


def test_missing_network_does_not_block_visual_pass() -> None:
    no_network = replace(WINNING_SPIN, network=None)
    assert set(statuses(evaluate_completed_spin(no_network)).values()) == {Status.PASS}


def test_wrong_currency_fails() -> None:
    pen = replace(WINNING_SPIN, market_currency="PEN")
    assert statuses(evaluate_completed_spin(pen))[Check.CURRENCY_MATCHES.value] is Status.FAIL


def test_real_rejected_spin_passes_every_check() -> None:
    results = evaluate_insufficient_balance(REJECTED_SPIN)
    assert set(statuses(results).values()) == {Status.PASS}


def test_missing_message_fails_scenario_two() -> None:
    silent = replace(REJECTED_SPIN, screen_after=screen("0.00", "0.20"))
    result = statuses(evaluate_insufficient_balance(silent))
    assert result[Check.INSUFFICIENT_MESSAGE_SHOWN.value] is Status.FAIL
    assert result[Check.SPIN_REJECTED.value] is Status.FAIL


def test_spin_sent_to_server_contradicts_rejection() -> None:
    sent = replace(REJECTED_SPIN, network=NetworkSummary(spin_requested=True))
    assert statuses(evaluate_insufficient_balance(sent))[Check.SPIN_REJECTED.value] is Status.FAIL


# --- Regresiones de la auditoría del equipo (15/10) ---------------------------------------------

EVENTS = GameEventsSummary(
    received=True,
    round_started=True,
    round_ended=True,
    bet=Decimal("0.20"),
    win=Decimal("0.15"),
    balance_before=Decimal("64.70"),
    balance_after=Decimal("64.65"),
    languages=("es",),
    currencies=("EUR",),
)


def test_header_currency_alone_does_not_pass_without_hud_currency() -> None:
    blind = replace(
        WINNING_SPIN,
        screen_before=replace(WINNING_SPIN.screen_before, currencies_seen=()),
        screen_after=replace(WINNING_SPIN.screen_after, currencies_seen=()),
    )
    assert statuses(evaluate_completed_spin(blind))[Check.CURRENCY_MATCHES.value] is Status.FAIL


def test_mixed_currencies_on_screen_fail() -> None:
    mixed = replace(
        WINNING_SPIN,
        screen_after=replace(WINNING_SPIN.screen_after, currencies_seen=("EUR", "USD")),
    )
    assert statuses(evaluate_completed_spin(mixed))[Check.CURRENCY_MATCHES.value] is Status.FAIL


def test_mixed_currencies_in_game_events_are_a_discrepancy() -> None:
    mixed = replace(WINNING_SPIN, events=replace(EVENTS, currencies=("EUR", "USD")))
    assert statuses(evaluate_completed_spin(mixed))[Check.CURRENCY_MATCHES.value] is Status.FAIL


def test_mixed_languages_in_game_events_are_a_discrepancy() -> None:
    mixed = replace(REJECTED_SPIN, events=replace(EVENTS, languages=("en", "es")))
    result = statuses(evaluate_insufficient_balance(mixed))
    assert result[Check.INSUFFICIENT_MESSAGE_SHOWN.value] is Status.FAIL


def test_incoherent_game_events_contradict() -> None:
    broken = replace(WINNING_SPIN, events=replace(EVENTS, anomalies=("2 rondas terminadas",)))
    result = statuses(evaluate_completed_spin(broken))
    assert result[Check.SPIN_COMPLETED.value] is Status.FAIL


def test_server_win_must_match_screen_win() -> None:
    wrong = replace(WINNING_SPIN, network=replace(SERVER, declared_win=Decimal("0.30")))
    result = statuses(evaluate_completed_spin(wrong))
    assert result[Check.GAME_BALANCE_CONSISTENT.value] is Status.FAIL
    assert result[Check.BETSSON_BALANCE_RECONCILES.value] is Status.FAIL


def test_requested_but_not_accepted_wager_is_not_confirmed() -> None:
    unconfirmed = replace(WINNING_SPIN, network=replace(SERVER, wager_accepted=None))
    result = {r.check: r for r in evaluate_completed_spin(unconfirmed)}
    wager = result[Check.WAGER_MATCHES.value]
    assert "el servidor no confirmó la apuesta" in str(wager.testimonies)


def test_accepted_wager_different_from_screen_is_a_discrepancy() -> None:
    wrong = replace(WINNING_SPIN, network=replace(SERVER, wager_accepted=Decimal("0.40")))
    assert statuses(evaluate_completed_spin(wrong))[Check.WAGER_MATCHES.value] is Status.FAIL


def test_rejection_message_after_a_spin_fails_scenario_one() -> None:
    rejected = replace(
        WINNING_SPIN,
        screen_after=replace(WINNING_SPIN.screen_after, message="Fondos insuficientes"),
    )
    assert statuses(evaluate_completed_spin(rejected))[Check.SPIN_COMPLETED.value] is Status.FAIL


def test_message_already_visible_before_spinning_does_not_prove_rejection() -> None:
    stale = replace(
        REJECTED_SPIN,
        screen_before=replace(REJECTED_SPIN.screen_before, message="Fondos insuficientes"),
    )
    assert statuses(evaluate_insufficient_balance(stale))[Check.SPIN_REJECTED.value] is Status.FAIL
