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
from betsson_validator.domain.money import Money, expected_amount_after
from betsson_validator.domain.verdict import (
    CheckResult,
    Outcome,
    Testimony,
    WitnessKind,
    evaluate,
)
from betsson_validator.scenarios.evidence import GameEventsSummary, NetworkSummary, RunEvidence

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
    if events.anomalies:
        return _t(
            EVENTS,
            WitnessKind.CORROBORATING,
            False,
            f"eventos incoherentes: {'; '.join(events.anomalies)}",
            (events.evidence,) if events.evidence else (),
        )
    ok, detail = judge(events)
    evidence_files = (events.evidence,) if events.evidence else ()
    return _t(EVENTS, WitnessKind.CORROBORATING, ok, detail, evidence_files)


def _same(a: Decimal | None, b: Decimal | None) -> bool | None:
    return None if a is None or b is None else a == b


def _all(*verdicts: bool | None) -> bool | None:
    """Une varias comparaciones: falla si alguna falla; sin datos si ninguna se pudo hacer."""
    known = [v for v in verdicts if v is not None]
    return None if not known else all(known)


def _only(values: tuple[str, ...], expected: str) -> bool | None:
    """Todos los valores comunicados son el esperado (uno distinto mezclado es un fallo)."""
    return None if not values else set(values) == {expected}


# --- Comprobaciones compartidas ---------------------------------------------------------------


def currency_matches(evidence: RunEvidence) -> CheckResult:
    expected = evidence.market_currency
    seen = tuple(
        sorted({*evidence.screen_before.currencies_seen, *evidence.screen_after.currencies_seen})
    )
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        _only(seen, expected),
        f"divisa leída en el HUD del juego: {', '.join(seen) or 'no leída'}; esperada {expected}",
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    # La cabecera es de Betsson, no del juego: corrobora, pero no sustituye a lo que muestra el HUD.
    header_currency = evidence.betsson_before.currency if evidence.betsson_before else None
    header = _t(
        HEADER,
        WitnessKind.CORROBORATING,
        None if header_currency is None else header_currency == expected,
        f"divisa del saldo de Betsson: {header_currency or 'no leída'}",
        evidence.betsson_evidence,
    )
    events = _events(
        evidence,
        lambda e: (
            _only(e.currencies, expected),
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
    shown = evidence.screen_after.message or evidence.screen_after.notice
    testimonies = [
        _t(
            MOTION,
            WitnessKind.VISUAL,
            motion.completed,
            detail,
            (*motion.evidence, evidence.screen_after.evidence),
        ),
        _t(
            SCREEN,
            WitnessKind.VISUAL,
            shown is None,
            "sin mensajes de rechazo ni avisos tras la tirada"
            if shown is None
            else f"el juego mostró «{shown}»",
            (evidence.screen_after.evidence,),
        ),
    ]
    network = evidence.network
    if network is None or not network.reliable:
        testimonies.append(
            _t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible o incompleto")
        )
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
                None
                if not (e.round_started or e.round_ended)
                else e.round_started and e.round_ended,
                "el juego anunció el inicio y el fin de la ronda"
                if e.round_started and e.round_ended
                else "el juego no comunicó ninguna ronda"
                if not (e.round_started or e.round_ended)
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
    if network is None or network.wager_accepted is None or shown is None:
        server = _t(SERVER, WitnessKind.CORROBORATING, None, "el servidor no confirmó la apuesta")
    else:
        server = _t(
            SERVER,
            WitnessKind.CORROBORATING,
            _all(
                network.wager_accepted == shown.amount,
                _same(network.wager_requested, shown.amount),
            ),
            f"apuesta pedida {_fmt(network.wager_requested)} y aceptada por el servidor "
            f"{_fmt(network.wager_accepted)} (moneda x líneas)",
            (network.evidence,) if network.evidence else (),
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
    if not evidence.screen_after.settled:
        screen_ok, detail = None, "el marcador del juego no se estabilizó a tiempo para leerlo"
    elif before is None or after is None or bet is None:
        screen_ok, detail = None, "no se pudo leer el crédito o la apuesta"
    else:
        expected = expected_amount_after(before.amount, bet.amount, win)
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
    server = _server_round(evidence, after.amount if after else None, win)
    events = _events(
        evidence,
        lambda e: (
            _all(_same(e.balance_after, after.amount if after else None), _same(e.win, win)),
            f"saldo final {_fmt(e.balance_after)} y premio {_fmt(e.win)} comunicados por el juego",
        ),
    )
    return evaluate(Check.GAME_BALANCE_CONSISTENT.value, (screen, server, events))


def _server_round(evidence: RunEvidence, credit_after: Decimal | None, win: Decimal) -> Testimony:
    """El servidor: su saldo final, su premio declarado (tw) y su propia cuenta deben cuadrar."""
    network = evidence.network
    if network is None or network.balance_after is None:
        return _t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible")
    before, wager, declared = network.balance_before, network.wager_accepted, network.declared_win
    internal = (
        None
        if before is None or wager is None or declared is None
        else expected_amount_after(before, wager, declared) == network.balance_after
    )
    return _t(
        SERVER,
        WitnessKind.CORROBORATING,
        _all(
            _same(network.balance_after, credit_after), _same(network.declared_win, win), internal
        ),
        f"saldo {_fmt(network.balance_before)} → {_fmt(network.balance_after)}, apuesta "
        f"aceptada {_fmt(network.wager_accepted)} y premio declarado {_fmt(network.declared_win)} "
        "según el servidor del juego",
        (network.evidence,) if network.evidence else (),
    )


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
        expected = expected_amount_after(before.amount, bet.amount, win)
        header_ok = after.amount == expected
        detail = (
            f"saldo {before} - apuesta {bet.amount} + premio {win} = {expected}; "
            f"Betsson muestra {after}"
        )
    header = _t(HEADER, WitnessKind.VISUAL, header_ok, detail, evidence.betsson_evidence)
    game_credit = evidence.screen_after.credit if evidence.screen_after.settled else None
    game_ok = None if game_credit is None or after is None else game_credit.amount == after.amount
    game = _t(
        SCREEN,
        WitnessKind.CORROBORATING,
        game_ok,
        f"crédito del juego tras la tirada {_fmt(game_credit)} frente a Betsson {_fmt(after)}",
        (evidence.screen_after.evidence,),
    )
    network = evidence.network
    wager = network.wager_accepted if network else None
    declared = network.declared_win if network else None
    if wager is None or declared is None or before is None:
        server = _t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible")
    else:
        expected_server = expected_amount_after(before.amount, wager, declared)
        server = _t(
            SERVER,
            WitnessKind.CORROBORATING,
            after is not None and after.amount == expected_server,
            f"apuesta aceptada {wager} y premio declarado {declared} por el servidor "
            f"→ {expected_server}",
        )

    def judge_events(e: GameEventsSummary) -> tuple[bool | None, str]:
        if e.bet is None or e.win is None or before is None or after is None:
            return None, "el juego no comunicó apuesta y premio"
        expected_events = expected_amount_after(before.amount, e.bet, e.win)
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
    # El mensaje debe aparecer como respuesta al giro: si ya estaba antes, no prueba el rechazo.
    already_shown = evidence.screen_before.message is not None
    notice = (
        f"; aviso del juego «{evidence.screen_after.notice}»"
        if evidence.screen_after.notice
        else ""
    )
    settled = evidence.screen_after.settled
    unchanged = None if before is None or after is None or not settled else before == after
    screen_ok = None if unchanged is None else unchanged and message is not None
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        False if already_shown else screen_ok,
        f"mensaje de rechazo {'visible' if message else 'no visible'}"
        f"{' (ya estaba antes de girar)' if already_shown else ''}{notice}; "
        f"crédito {_fmt(before)} → {_fmt(after)}",
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    motion = _t(
        MOTION,
        WitnessKind.CORROBORATING,
        not evidence.motion.completed,
        "sin animación de giro completo"
        if not evidence.motion.completed
        else "el juego animó un giro completo",
    )
    server = _server_rejection(evidence.network)
    events = _events(
        evidence,
        lambda e: (
            None
            if not (e.low_balance or e.round_started)
            else e.low_balance and not e.round_started,
            "el juego avisó de saldo insuficiente y no inició ninguna ronda"
            if e.low_balance and not e.round_started
            else "el juego inició una ronda"
            if e.round_started
            else "el juego no comunicó nada sobre la tirada",
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
            _only(e.languages, language),
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
    settled = evidence.screen_after.settled
    screen = _t(
        SCREEN,
        WitnessKind.VISUAL,
        None if before is None or after is None or not settled else before == after,
        f"crédito del juego {_fmt(before)} → {_fmt(after)}"
        + ("" if settled else " (el marcador no se estabilizó: no vale como prueba)"),
        (evidence.screen_before.evidence, evidence.screen_after.evidence),
    )
    server = _server_rejection(evidence.network)
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


def _server_rejection(network: NetworkSummary | None) -> Testimony:
    """El servidor no cobró ninguna tirada: o no se le pidió, o la rechazó sin aceptarla.

    Solo cuenta si la captura es fiable: sin tráfico observado o con respuestas ilegibles, la
    ausencia de una tirada no prueba nada.
    """
    evidence = (network.evidence,) if network and network.evidence else ()
    if network is None or not network.reliable:
        return _t(SERVER, WitnessKind.CORROBORATING, None, "tráfico no disponible o incompleto")
    if not network.spin_requested:
        return _t(SERVER, WitnessKind.CORROBORATING, True, "no se envió ninguna tirada", evidence)
    if network.wager_accepted is None:
        # Sin un rechazo explícito del proveedor, una tirada pedida y no aceptada es desconocida.
        return _t(
            SERVER,
            WitnessKind.CORROBORATING,
            None,
            "se pidió una tirada y el servidor no confirmó ni su aceptación ni su rechazo",
            evidence,
        )
    return _t(
        SERVER,
        WitnessKind.CORROBORATING,
        False,
        f"el servidor aceptó una tirada de {network.wager_accepted}",
        evidence,
    )


def evaluate_insufficient_balance(evidence: RunEvidence) -> tuple[CheckResult, ...]:
    return (
        spin_rejected(evidence),
        insufficient_message_shown(evidence),
        currency_matches(evidence),
        betsson_balance_unchanged(evidence),
        game_balance_unchanged(evidence),
    )
