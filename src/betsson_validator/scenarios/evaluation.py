"""Comprobaciones oficiales evaluadas con testigos independientes (decisión 001).

Testigos:
- "pantalla del juego" y "cabecera de Betsson": lo que ve el jugador (VISUAL).
- "movimiento de los rodillos": actividad visual del juego (VISUAL).
- "servidor del juego": tráfico gameService observado (CORROBORATING).
- "eventos del juego": lo que el juego comunica al casino por postMessage (CORROBORATING).
"""

from collections.abc import Callable
from decimal import Decimal

from betsson_validator.domain.checks import Check
from betsson_validator.domain.money import Money
from betsson_validator.domain.verdict import (
    CheckResult,
    Outcome,
    Testimony,
    WitnessKind,
    evaluate,
)
from betsson_validator.scenarios.evidence import GameEventsSummary, RunEvidence

SCREEN = "pantalla del juego"
HEADER = "cabecera de Betsson"
MOTION = "movimiento de los rodillos"
SERVER = "servidor del juego"
EVENTS = "eventos del juego"

_ZERO = Decimal("0")


def _t(
    witness: str, kind: WitnessKind, ok: bool | None, detail: str, evidence: tuple[str, ...] = ()
) -> Testimony:
    outcome = Outcome.UNAVAILABLE if ok is None else Outcome.CONFIRMS if ok else Outcome.CONTRADICTS
    return Testimony(witness=witness, kind=kind, outcome=outcome, detail=detail, evidence=evidence)


def _fmt(value: Money | Decimal | None) -> str:
    return "no leído" if value is None else str(value)


def _win(evidence: RunEvidence) -> Decimal:
    """Premio visible en pantalla; si el juego no muestra ganancia, la tirada no pagó."""
    after = evidence.screen_after
    return after.win.amount if after.win is not None else _ZERO


def _events(
    evidence: RunEvidence,
    judge: Callable[[GameEventsSummary], tuple[bool | None, str]],
) -> Testimony:
    """Testimonio del canal postMessage juego → casino, si se recibió algo."""
    events = evidence.events
    if events is None or not events.received:
        return _t(EVENTS, WitnessKind.CORROBORATING, None, "no se recibieron eventos del juego")
    ok, detail = judge(events)
    evidence_files = (events.evidence,) if events.evidence else ()
    return _t(EVENTS, WitnessKind.CORROBORATING, ok, detail, evidence_files)


def _same(a: Decimal | None, b: Decimal | None) -> bool | None:
    return None if a is None or b is None else a == b


# --- Comprobaciones compartidas ---------------------------------------------------------------


def currency_matches(evidence: RunEvidence) -> CheckResult:
    expected = evidence.market_currency
    seen = evidence.screen_before.currency_seen
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        None if seen is None else seen == expected,
        f"divisa leída en el HUD: {seen or 'no leída'}; esperada {expected}",
        (evidence.screen_before.evidence,),
    )
    header_currency = evidence.betsson_before.currency if evidence.betsson_before else None
    header = _t(
        HEADER,
        WitnessKind.VISUAL,
        None if header_currency is None else header_currency == expected,
        f"divisa del saldo de Betsson: {header_currency or 'no leída'}",
        evidence.betsson_evidence,
    )
    events = _events(
        evidence,
        lambda e: (
            (expected in e.currencies) if e.currencies else None,
            f"divisa comunicada por el juego: {', '.join(e.currencies) or 'ninguna'}",
        ),
    )
    return evaluate(Check.CURRENCY_MATCHES.value, (screen, header, events))


# --- Escenario 1: tirada completada ------------------------------------------------------------


def spin_completed(evidence: RunEvidence) -> CheckResult:
    motion = evidence.motion
    if motion.completed:
        detail = f"el juego se movió y volvió al reposo ({motion.samples} capturas)"
    elif motion.started:
        detail = "el giro empezó pero no terminó dentro del tiempo límite"
    else:
        detail = "el juego no reaccionó al botón de girar"
    testimonies = [
        _t(MOTION, WitnessKind.VISUAL, motion.completed, detail, (evidence.screen_after.evidence,))
    ]
    network = evidence.network
    if network is None:
        testimonies.append(_t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible"))
    else:
        testimonies.append(
            _t(
                SERVER,
                WitnessKind.CORROBORATING,
                network.spin_requested and network.settled,
                "tirada liquidada (na=s)"
                if network.settled
                else "el servidor no liquidó ninguna tirada",
                (network.evidence,) if network.evidence else (),
            )
        )
    testimonies.append(
        _events(
            evidence,
            lambda e: (
                e.round_started and e.round_ended,
                "el juego anunció el inicio y el fin de la ronda"
                if e.round_started and e.round_ended
                else "el juego no anunció una ronda completa",
            ),
        )
    )
    return evaluate(Check.SPIN_COMPLETED.value, tuple(testimonies))


def wager_matches(evidence: RunEvidence) -> CheckResult:
    shown = evidence.screen_before.bet
    after = evidence.screen_after.bet
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        None if shown is None or after is None else shown == after,
        f"apuesta mostrada antes {_fmt(shown)} y después {_fmt(after)}",
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    network = evidence.network
    server_ok = (
        None
        if network is None or network.wager is None or shown is None
        else network.wager == shown.amount
    )
    server = _t(
        SERVER,
        WitnessKind.CORROBORATING,
        server_ok,
        "apuesta cobrada por el servidor (moneda x líneas): "
        f"{_fmt(network.wager if network else None)}",
    )
    events = _events(
        evidence,
        lambda e: (
            _same(e.bet, shown.amount if shown else None),
            f"apuesta comunicada por el juego: {_fmt(e.bet)}",
        ),
    )
    return evaluate(Check.WAGER_MATCHES.value, (screen, server, events))


def game_balance_consistent(evidence: RunEvidence) -> CheckResult:
    before, after, bet = (
        evidence.screen_before.credit,
        evidence.screen_after.credit,
        evidence.screen_before.bet,
    )
    win = _win(evidence)
    if before is None or after is None or bet is None:
        screen_ok, detail = None, "no se pudo leer el crédito o la apuesta"
    else:
        expected = before.amount - bet.amount + win
        screen_ok = after.amount == expected
        detail = (
            f"crédito {before} - apuesta {bet.amount} + premio {win} = {expected}; leído {after}"
        )
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        screen_ok,
        detail,
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    network = evidence.network
    server_ok = (
        None
        if network is None or network.balance_after is None or after is None
        else network.balance_after == after.amount
    )
    server = _t(
        SERVER,
        WitnessKind.CORROBORATING,
        server_ok,
        "saldo final según el servidor del juego: "
        f"{_fmt(network.balance_after if network else None)}",
    )
    events = _events(
        evidence,
        lambda e: (
            _same(e.balance_after, after.amount if after else None),
            f"saldo final comunicado por el juego: {_fmt(e.balance_after)}",
        ),
    )
    return evaluate(Check.GAME_BALANCE_CONSISTENT.value, (screen, server, events))


def betsson_balance_reconciles(evidence: RunEvidence) -> CheckResult:
    before, after, bet = (
        evidence.betsson_before,
        evidence.betsson_after,
        evidence.screen_before.bet,
    )
    win = _win(evidence)
    if before is None or after is None or bet is None:
        header_ok, detail = None, "no se pudo leer el saldo de Betsson o la apuesta"
    else:
        expected = before.amount - bet.amount + win
        header_ok = after.amount == expected
        detail = (
            f"saldo {before} - apuesta {bet.amount} + premio {win} = {expected}; "
            f"Betsson muestra {after}"
        )
    header = _t(HEADER, WitnessKind.VISUAL, header_ok, detail, evidence.betsson_evidence)
    game_credit = evidence.screen_after.credit
    game_ok = None if game_credit is None or after is None else game_credit.amount == after.amount
    game = _t(
        SCREEN,
        WitnessKind.CORROBORATING,
        game_ok,
        f"crédito del juego tras la tirada {_fmt(game_credit)} frente a Betsson {_fmt(after)}",
        (evidence.screen_after.evidence,),
    )
    network = evidence.network
    if network is None or network.wager is None or network.payout is None or before is None:
        server = _t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible")
    else:
        expected_server = before.amount - network.wager + network.payout
        server = _t(
            SERVER,
            WitnessKind.CORROBORATING,
            after is not None and after.amount == expected_server,
            f"apuesta {network.wager} y premio {network.payout} según el servidor "
            f"→ {expected_server}",
        )

    def judge_events(e: GameEventsSummary) -> tuple[bool | None, str]:
        if e.bet is None or e.win is None or before is None or after is None:
            return None, "el juego no comunicó apuesta y premio"
        expected_events = before.amount - e.bet + e.win
        return (
            after.amount == expected_events,
            f"apuesta {e.bet} y premio {e.win} según el juego → {expected_events}",
        )

    events = _events(evidence, judge_events)
    return evaluate(Check.BETSSON_BALANCE_RECONCILES.value, (header, game, server, events))


def evaluate_completed_spin(evidence: RunEvidence) -> tuple[CheckResult, ...]:
    return (
        spin_completed(evidence),
        wager_matches(evidence),
        currency_matches(evidence),
        game_balance_consistent(evidence),
        betsson_balance_reconciles(evidence),
    )


# --- Escenario 2: saldo insuficiente -----------------------------------------------------------


def spin_rejected(evidence: RunEvidence) -> CheckResult:
    before, after = evidence.screen_before.credit, evidence.screen_after.credit
    message = evidence.screen_after.message
    unchanged = None if before is None or after is None else before == after
    screen_ok = None if unchanged is None else unchanged and message is not None
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        screen_ok,
        f"mensaje de rechazo {'visible' if message else 'no visible'}; "
        f"crédito {_fmt(before)} → {_fmt(after)}",
        (evidence.screen_after.evidence,),
    )
    motion = _t(
        MOTION,
        WitnessKind.CORROBORATING,
        not evidence.motion.completed,
        "sin animación de giro completo"
        if not evidence.motion.completed
        else "el juego animó un giro completo",
    )
    network = evidence.network
    server = _t(
        SERVER,
        WitnessKind.CORROBORATING,
        None if network is None else not network.spin_requested,
        "tráfico no disponible"
        if network is None
        else "no se envió ninguna tirada al servidor"
        if not network.spin_requested
        else "el cliente envió una tirada al servidor",
    )
    events = _events(
        evidence,
        lambda e: (
            e.low_balance and not e.round_started,
            "el juego avisó de saldo insuficiente y no inició ninguna ronda"
            if e.low_balance and not e.round_started
            else "el juego inició una ronda"
            if e.round_started
            else "el juego no avisó de saldo insuficiente",
        ),
    )
    return evaluate(Check.SPIN_REJECTED.value, (screen, motion, server, events))


def insufficient_message_shown(evidence: RunEvidence) -> CheckResult:
    message = evidence.screen_after.message
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        message is not None,
        f"mensaje leído: «{message}»"
        if message
        else "no apareció el mensaje de saldo insuficiente",
        (evidence.screen_after.evidence,),
    )
    language = evidence.market_language.lower()
    events = _events(
        evidence,
        lambda e: (
            (language in e.languages) if e.languages else None,
            f"idioma del juego: {', '.join(e.languages) or 'no comunicado'}; esperado {language}",
        ),
    )
    return evaluate(Check.INSUFFICIENT_MESSAGE_SHOWN.value, (screen, events))


def betsson_balance_unchanged(evidence: RunEvidence) -> CheckResult:
    before, after = evidence.betsson_before, evidence.betsson_after
    header = _t(
        HEADER,
        WitnessKind.VISUAL,
        None if before is None or after is None else before == after,
        f"saldo de Betsson {_fmt(before)} → {_fmt(after)}",
        evidence.betsson_evidence,
    )
    return evaluate(Check.BETSSON_BALANCE_UNCHANGED.value, (header,))


def game_balance_unchanged(evidence: RunEvidence) -> CheckResult:
    before, after = evidence.screen_before.credit, evidence.screen_after.credit
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        None if before is None or after is None else before == after,
        f"crédito del juego {_fmt(before)} → {_fmt(after)}",
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    network = evidence.network
    server = _t(
        SERVER,
        WitnessKind.CORROBORATING,
        None if network is None else not network.spin_requested,
        "sin tirada en el servidor, el saldo no pudo cambiar"
        if network is not None and not network.spin_requested
        else "tráfico no disponible"
        if network is None
        else "hubo una tirada en el servidor",
    )
    events = _events(
        evidence,
        lambda e: (
            not e.round_started,
            "el juego no inició ninguna ronda"
            if not e.round_started
            else "el juego inició una ronda",
        ),
    )
    return evaluate(Check.GAME_BALANCE_UNCHANGED.value, (screen, server, events))


def evaluate_insufficient_balance(evidence: RunEvidence) -> tuple[CheckResult, ...]:
    return (
        spin_rejected(evidence),
        insufficient_message_shown(evidence),
        currency_matches(evidence),
        betsson_balance_unchanged(evidence),
        game_balance_unchanged(evidence),
    )
