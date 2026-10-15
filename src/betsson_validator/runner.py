"""Ejecuta un escenario de principio a fin: navegador → login → juego → tirada → informe.

Coordina las piezas sin contener lógica de negocio: la evaluación vive en scenarios/evaluation.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from betsson_validator.browser import BrowserSettings, browser_context, tracing
from betsson_validator.casino.betsson import BetssonCasino
from betsson_validator.config.market import AccountEnv, MarketConfig
from betsson_validator.config.provider import ProviderConfig
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import detect_currency
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import CheckResult
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.events import GameEventRecorder
from betsson_validator.game.player import ScreenGame, ScreenModel, ScreenObservation
from betsson_validator.perception.learner import ScreenLearner
from betsson_validator.perception.ocr import TextReader
from betsson_validator.profiles import DEFAULT_PROFILES_DIR, load_profile
from betsson_validator.providers.pragmatic.events import loading_finished, summarize_events
from betsson_validator.providers.pragmatic.network import (
    GameServiceCall,
    NoSpinObservedError,
    balance_from_init,
    summarize_round,
)
from betsson_validator.providers.pragmatic.recorder import GameServiceRecorder
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
from betsson_validator.security import audit_and_quarantine, scrub_trace

Evaluator = Callable[[RunEvidence], tuple[CheckResult, ...]]


@dataclass(frozen=True)
class ScenarioPlan:
    account: Callable[[MarketConfig], AccountEnv]
    evaluator: Evaluator
    dismiss_message: bool


PLANS: dict[Scenario, ScenarioPlan] = {
    Scenario.COMPLETED_SPIN: ScenarioPlan(
        account=lambda market: market.accounts.funded,
        evaluator=evaluate_completed_spin,
        dismiss_message=False,
    ),
    Scenario.INSUFFICIENT_BALANCE: ScenarioPlan(
        account=lambda market: market.accounts.no_balance,
        evaluator=evaluate_insufficient_balance,
        dismiss_message=True,
    ),
}


class SafetyStopError(RuntimeError):
    """Parada preventiva antes de arriesgar dinero real."""


class ProfileMissingError(RuntimeError):
    """El juego aún no tiene perfil aprendido."""


def _snapshot(observation: ScreenObservation) -> ScreenSnapshot:
    hud = observation.hud
    seen = next(
        (
            currency
            for reading in (hud.credit, hud.bet)
            if reading is not None and (currency := detect_currency(reading.source_text))
        ),
        None,
    )
    return ScreenSnapshot(
        credit=hud.credit.money if hud.credit else None,
        bet=hud.bet.money if hud.bet else None,
        win=hud.win.money if hud.win else None,
        currency_seen=seen,
        message=observation.message,
        evidence=observation.evidence,
    )


def _network_summary(
    before: list[GameServiceCall], during: list[GameServiceCall], evidence: str
) -> NetworkSummary:
    try:
        balance_before = balance_from_init(before)
        spin = summarize_round(during, balance_before or Decimal(0))
    except NoSpinObservedError:
        return NetworkSummary(spin_requested=False, evidence=evidence)
    return NetworkSummary(
        spin_requested=True,
        settled=spin.settled,
        wager=spin.wager,
        balance_before=balance_before,
        balance_after=spin.balance_after,
        payout=spin.payout if balance_before is not None else None,
        evidence=evidence,
    )


def _sanitize(message: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "<SECRETO>")
    return message.splitlines()[0][:500] if message else "Error desconocido"


@dataclass(frozen=True)
class RunContext:
    """Todo lo que necesita una ejecución, inyectado desde fuera (CLI o tests)."""

    market: MarketConfig
    provider: ProviderConfig
    game: str
    settings: BrowserSettings
    reader: TextReader
    out_dir: Path
    learner: ScreenLearner | None = None
    profiles_dir: Path = DEFAULT_PROFILES_DIR


def run_scenario(scenario: Scenario, ctx: RunContext) -> ScenarioRun:
    plan = PLANS[scenario]
    evidence_dir = ctx.out_dir / scenario.value
    files = EvidenceRecorder(evidence_dir)
    started = datetime.now(UTC)
    secrets: tuple[str, ...] = ()
    results: tuple[CheckResult, ...] = ()
    notes: list[str] = []
    error: str | None = None
    try:
        profile = load_profile(ctx.provider.id, ctx.game, ctx.profiles_dir)
        if profile is None:
            raise ProfileMissingError(
                f"El juego '{ctx.game}' no tiene perfil aprendido. Ejecuta: "
                f"python -m betsson_validator learn --provider {ctx.provider.id} --game {ctx.game}"
            )
        credentials = plan.account(ctx.market).resolve()
        secrets = (credentials.email.get_secret_value(), credentials.password.get_secret_value())
        with browser_context(ctx.settings, evidence_dir) as context:
            events = (
                GameEventRecorder(context) if ctx.provider.events_witness == "pragmatic" else None
            )
            page = context.new_page()
            network = (
                GameServiceRecorder(context)
                if ctx.provider.network_witness == "pragmatic"
                else None
            )
            casino = BetssonCasino(page, ctx.market, typing_delay_ms=ctx.settings.slow_typing_ms)
            casino.open()
            casino.login(credentials)
            model = ScreenModel(
                profile=profile,
                reader=ctx.reader,
                currency=ctx.market.currency,
                learner=ctx.learner,
            )
            with tracing(context, evidence_dir / "trace.zip"):
                try:
                    results = _play(
                        casino,
                        ctx,
                        plan=plan,
                        model=model,
                        network=network,
                        events=events,
                        files=files,
                    )
                finally:
                    notes = list(model.notes)
                    if model.notes:
                        model.profile.save(evidence_dir / "perfil_propuesto")
    except Exception as exception:  # el informe debe recoger cualquier fallo, sin secretos
        error = _sanitize(f"{type(exception).__name__}: {exception}", secrets)
    scrub_trace(evidence_dir / "trace.zip", secrets)
    quarantined = audit_and_quarantine(evidence_dir, secrets)
    return ScenarioRun(
        scenario=scenario,
        market=ctx.market.id,
        provider=ctx.provider.filter_label,
        game=ctx.game,
        started_at=started,
        finished_at=datetime.now(UTC),
        results=results,
        error=error,
        quarantined=tuple(quarantined),
        notes=tuple(notes),
    )


def _play(
    casino: BetssonCasino,
    ctx: RunContext,
    *,
    plan: ScenarioPlan,
    model: ScreenModel,
    network: GameServiceRecorder | None,
    events: GameEventRecorder | None,
    files: EvidenceRecorder,
) -> tuple[CheckResult, ...]:
    betsson_before = casino.read_balance()
    header_before = casino.capture_balance(files.directory / "00_saldo_betsson_antes.png")

    handle = casino.launch_game(ctx.provider, ctx.game)
    game = ScreenGame(
        page=casino.page,
        handle=handle,
        model=model,
        evidence=files,
        message_pattern=re.compile(ctx.market.ui.insufficient_funds_pattern),
        dismiss_labels=ctx.market.ui.dismiss_labels,
        loading_finished=(
            (lambda: loading_finished(GameEventRecorder.collect(casino.page))) if events else None
        ),
    )
    game.wait_until_ready()
    ready = game.set_minimum_bet()
    bet = ready.hud.bet.money if ready.hud.bet else None
    if bet is None or bet.amount > ctx.provider.max_bet:
        raise SafetyStopError(
            f"Apuesta mostrada {bet or 'no leída'}: supera el máximo de seguridad "
            f"{ctx.provider.max_bet} o no se pudo leer. No se gira."
        )

    mark = network.mark() if network else 0
    events_mark = len(GameEventRecorder.collect(casino.page)) if events else 0
    spin = game.spin_and_watch()
    after = game.observe_settled("despues_de_girar")
    events_summary: GameEventsSummary | None = None
    if events is not None:  # se leen ANTES de salir de la página del juego
        game_events = GameEventRecorder.collect(casino.page)[events_mark:]
        events_file = files.save_json("eventos_del_juego", game_events)
        events_summary = summarize_events(game_events, str(events_file))
    if plan.dismiss_message and after.message:
        game.dismiss_message()

    summary: NetworkSummary | None = None
    if network is not None:
        traffic = files.save_json("trafico_juego_sin_tokens", network.redacted_log())
        calls = network.calls
        summary = _network_summary(calls[:mark], calls[mark:], str(traffic))

    betsson_after = casino.read_balance_after(betsson_before)
    header_after = casino.capture_balance(files.directory / "99_saldo_betsson_despues.png")

    evidence = RunEvidence(
        market_currency=ctx.market.currency,
        betsson_before=betsson_before,
        betsson_after=betsson_after,
        betsson_evidence=(str(header_before), str(header_after)),
        screen_before=_snapshot(ready),
        screen_after=_snapshot(after),
        motion=MotionSummary(
            started=spin.lifecycle.started,
            completed=spin.lifecycle.completed,
            samples=len(spin.scores),
            peak=spin.lifecycle.peak_score,
        ),
        network=summary,
        events=events_summary,
        market_language=ctx.market.language,
    )
    files.save_json("resumen_observado", _describe(evidence, betsson_before, betsson_after))
    return plan.evaluator(evidence)


def _describe(evidence: RunEvidence, before: Money, after: Money) -> dict[str, object]:
    return {
        "betsson_before": str(before),
        "betsson_after": str(after),
        "screen_before": evidence.screen_before.__dict__,
        "screen_after": evidence.screen_after.__dict__,
        "motion": evidence.motion.__dict__,
        "network": evidence.network.__dict__ if evidence.network else None,
        "events": evidence.events.__dict__ if evidence.events else None,
    }
