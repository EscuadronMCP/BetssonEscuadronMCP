"""Ejecuta un escenario de principio a fin: navegador → login → juego → tirada → informe.

Coordina las piezas sin contener lógica de negocio: la evaluación vive en scenarios/evaluation,
las condiciones previas al giro en scenarios/preconditions y los testigos de cada proveedor en
providers/registry (el ejecutor no conoce a ningún proveedor concreto).
"""

import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from betsson_validator.browser import BrowserSettings, browser_context, tracing
from betsson_validator.casino.betsson import GAME_FRAME_SELECTOR, BetssonCasino
from betsson_validator.config.market import AccountEnv, MarketConfig
from betsson_validator.config.provider import ProviderConfig
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import detect_currency
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import CheckResult, withdraw_evidence
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.events import GameEventRecorder, capture_anomalies, payloads
from betsson_validator.game.player import ScreenGame, ScreenModel, ScreenObservation
from betsson_validator.locks import account_lock
from betsson_validator.perception.learner import ScreenLearner
from betsson_validator.perception.ocr import TextReader
from betsson_validator.profiles import DEFAULT_PROFILES_DIR, load_profile
from betsson_validator.providers.registry import (
    EventsInterpreter,
    NetworkWitness,
    events_interpreter,
    network_witness,
)
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
from betsson_validator.scenarios.faults import InjectedFault
from betsson_validator.scenarios.preconditions import (
    check_bet,
    require_funds,
    require_no_funds,
)
from betsson_validator.security import audit_and_quarantine, scrub_text, scrub_trace

Evaluator = Callable[[RunEvidence], tuple[CheckResult, ...]]


@dataclass(frozen=True)
class ScenarioPlan:
    account: Callable[[MarketConfig], AccountEnv]
    evaluator: Evaluator
    dismiss_message: bool
    # Comprueba saldo de Betsson, crédito del juego y apuesta antes de girar.
    precondition: Callable[[Money, Money | None, Money], None]


PLANS: dict[Scenario, ScenarioPlan] = {
    Scenario.COMPLETED_SPIN: ScenarioPlan(
        account=lambda market: market.accounts.funded,
        evaluator=evaluate_completed_spin,
        dismiss_message=False,
        precondition=require_funds,
    ),
    Scenario.INSUFFICIENT_BALANCE: ScenarioPlan(
        account=lambda market: market.accounts.no_balance,
        evaluator=evaluate_insufficient_balance,
        dismiss_message=True,
        precondition=require_no_funds,
    ),
}


class ProfileMissingError(RuntimeError):
    """El juego aún no tiene perfil aprendido."""


def _snapshot(observation: ScreenObservation) -> ScreenSnapshot:
    hud = observation.hud
    readings = [reading for reading in (hud.credit, hud.bet, hud.win) if reading is not None]
    currencies = {code for r in readings if (code := detect_currency(r.source_text))}
    return ScreenSnapshot(
        credit=hud.credit.money if hud.credit else None,
        bet=hud.bet.money if hud.bet else None,
        win=hud.win.money if hud.win else None,
        currencies_seen=tuple(sorted(currencies)),
        message=observation.message,
        evidence=observation.evidence,
        notice=observation.notice,
        settled=observation.settled,
    )


def _sanitize(message: str, secrets: tuple[str, ...]) -> str:
    clean = scrub_text(message, secrets)
    return clean.splitlines()[0][:500] if clean else "Error desconocido"


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
    # Solo para demostraciones: altera lo observado antes de evaluar (se anuncia en el informe).
    fault: InjectedFault | None = None


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
        interpreter = events_interpreter(ctx.provider.events_witness)
        with (
            account_lock(credentials.email.get_secret_value()),
            browser_context(ctx.settings, evidence_dir) as context,
        ):
            if interpreter is not None:
                GameEventRecorder(context, GAME_FRAME_SELECTOR)
            page = context.new_page()
            network = network_witness(ctx.provider.network_witness, context)
            casino = BetssonCasino(page, ctx.market, typing_delay_ms=ctx.settings.slow_typing_ms)
            casino.open()
            casino.login(credentials)
            model = ScreenModel(
                profile=profile,
                reader=ctx.reader,
                currency=ctx.market.currency,
                learner=ctx.learner,
                win_candidates=ctx.market.ui.win_label_candidates,
            )
            with tracing(context, evidence_dir / "trace.zip"):
                try:
                    results = _play(
                        casino,
                        ctx,
                        plan=plan,
                        model=model,
                        witnesses=_Witnesses(network, interpreter),
                        files=files,
                    )
                except Exception:
                    _save_failure_screen(casino, files)
                    raise
                finally:
                    notes = list(model.notes)
                    if model.notes:
                        model.profile.save(evidence_dir / "perfil_propuesto")
    except Exception as exception:  # el informe debe recoger cualquier fallo, sin secretos
        error = _sanitize(f"{type(exception).__name__}: {exception}", secrets)
    quarantined = _protect_evidence(evidence_dir, secrets, ctx.reader)
    removed = {str(evidence_dir / name) for name in quarantined}
    return ScenarioRun(
        scenario=scenario,
        market=ctx.market.id,
        provider=ctx.provider.filter_label,
        game=ctx.game,
        started_at=started,
        finished_at=datetime.now(UTC),
        results=tuple(withdraw_evidence(result, removed) for result in results),
        error=error,
        quarantined=tuple(quarantined),
        notes=tuple(notes),
        injected_fault=ctx.fault.description if ctx.fault else None,
    )


def _save_failure_screen(casino: BetssonCasino, files: EvidenceRecorder) -> None:
    """Captura de lo que había en pantalla al fallar: explica el error en el informe."""
    with suppress(Exception):  # sin captura no se pierde el error original
        casino.save_screenshot(files.directory / "fallo_pantalla.jpg")


def failed_run(scenario: Scenario, ctx: RunContext, error: BaseException) -> ScenarioRun:
    """Resultado FAIL para un escenario que no llegó a devolver el suyo (sin secretos)."""
    now = datetime.now(UTC)
    return ScenarioRun(
        scenario=scenario,
        market=ctx.market.id,
        provider=ctx.provider.filter_label,
        game=ctx.game,
        started_at=now,
        finished_at=now,
        results=(),
        error=_sanitize(f"{type(error).__name__}: {error}", ctx.market.accounts.secrets()),
    )


def _protect_evidence(
    evidence_dir: Path, secrets: tuple[str, ...], reader: TextReader
) -> list[str]:
    """Limpia la traza y retira cualquier evidencia con secretos (también si la traza está rota)."""
    trace = evidence_dir / "trace.zip"
    try:
        scrub_trace(trace, secrets)
    except Exception:  # traza ilegible: no se puede limpiar, así que no se publica
        trace.unlink(missing_ok=True)
    return audit_and_quarantine(evidence_dir, secrets, reader)


@dataclass(frozen=True)
class _Witnesses:
    """Testigos del proveedor disponibles en esta ejecución (pueden no existir)."""

    network: NetworkWitness | None
    events: EventsInterpreter | None


@dataclass(frozen=True)
class _Ready:
    betsson_before: Money
    header_before: Path
    game: ScreenGame
    observation: ScreenObservation


def _prepare(
    casino: BetssonCasino,
    ctx: RunContext,
    *,
    plan: ScenarioPlan,
    model: ScreenModel,
    witnesses: _Witnesses,
    files: EvidenceRecorder,
) -> _Ready:
    """Hasta justo antes de girar: saldo, juego cargado, apuesta mínima y condiciones previas."""
    betsson_before = casino.read_balance()
    header_before = casino.capture_balance(files.directory / "00_saldo_betsson_antes.jpg")
    handle = casino.launch_game(ctx.provider, ctx.game)
    events = witnesses.events
    game = ScreenGame(
        page=casino.page,
        handle=handle,
        model=model,
        evidence=files,
        message_pattern=re.compile(ctx.market.ui.insufficient_funds_pattern),
        notice_pattern=(
            re.compile(ctx.market.ui.game_notice_pattern)
            if ctx.market.ui.game_notice_pattern
            else None
        ),
        dismiss_labels=ctx.market.ui.dismiss_labels,
        loading_finished=(
            (lambda: events.loading_finished(payloads(GameEventRecorder.collect(casino.page))))
            if events
            else None
        ),
    )
    ready = game.set_minimum_bet(game.wait_until_ready())
    seen = _snapshot(ready)
    bet = check_bet(seen.bet, ctx.provider.max_bet, ctx.market.currency, seen.currencies_seen)
    plan.precondition(betsson_before, seen.credit, bet)
    return _Ready(betsson_before, header_before, game, ready)


def _play(
    casino: BetssonCasino,
    ctx: RunContext,
    *,
    plan: ScenarioPlan,
    model: ScreenModel,
    witnesses: _Witnesses,
    files: EvidenceRecorder,
) -> tuple[CheckResult, ...]:
    ready = _prepare(casino, ctx, plan=plan, model=model, witnesses=witnesses, files=files)
    game = ready.game
    mark = witnesses.network.mark() if witnesses.network else 0
    events_mark = len(GameEventRecorder.collect(casino.page)) if witnesses.events else 0
    spin = game.spin_and_watch()
    after = game.observe_settled("despues_de_girar")
    events_summary: GameEventsSummary | None = None
    if witnesses.events is not None:  # se leen ANTES de salir de la página del juego
        game_events = GameEventRecorder.collect(casino.page)[events_mark:]
        events_file = files.save_json("eventos_del_juego", game_events)
        events_summary = witnesses.events.summarize(payloads(game_events), str(events_file))
        problems = capture_anomalies(game_events, GameEventRecorder.dropped(casino.page))
        if problems:
            events_summary = replace(
                events_summary, anomalies=(*events_summary.anomalies, *problems)
            )
    if plan.dismiss_message and after.message:
        game.dismiss_message()

    network: NetworkSummary | None = None
    if witnesses.network is not None:
        traffic = files.save_json("trafico_juego_sin_tokens", witnesses.network.redacted_log())
        network = witnesses.network.summarize(mark, str(traffic))

    before_credit, after_credit = ready.observation.hud.credit, after.hud.credit
    credit_changed = (
        before_credit is None or after_credit is None or before_credit.money != after_credit.money
    )
    betsson_after = casino.read_balance_after(ready.betsson_before, expect_change=credit_changed)
    header_after = casino.capture_balance(files.directory / "99_saldo_betsson_despues.jpg")

    evidence = RunEvidence(
        market_currency=ctx.market.currency,
        betsson_before=ready.betsson_before,
        betsson_after=betsson_after,
        betsson_evidence=(str(ready.header_before), str(header_after)),
        screen_before=_snapshot(ready.observation),
        screen_after=_snapshot(after),
        motion=MotionSummary(
            started=spin.lifecycle.started,
            completed=spin.lifecycle.completed,
            samples=len(spin.scores),
            peak=spin.lifecycle.peak_score,
            evidence=spin.evidence,
        ),
        network=network,
        events=events_summary,
        market_language=ctx.market.language,
    )
    summary_data = _describe(evidence)  # siempre lo observado de verdad, sin el fallo inyectado
    summary_data["motion_scores"] = [round(score, 4) for score in spin.scores]
    summary_data["motion_thresholds"] = spin.thresholds.__dict__ if spin.thresholds else None
    if ctx.fault is not None:
        summary_data["injected_fault"] = ctx.fault.description
        evidence = ctx.fault.apply(evidence)
    files.save_json("resumen_observado", summary_data)
    return plan.evaluator(evidence)


def _describe(evidence: RunEvidence) -> dict[str, object]:
    return {
        "betsson_before": str(evidence.betsson_before),
        "betsson_after": str(evidence.betsson_after),
        "screen_before": evidence.screen_before.__dict__,
        "screen_after": evidence.screen_after.__dict__,
        "motion": evidence.motion.__dict__,
        "network": evidence.network.__dict__ if evidence.network else None,
        "events": evidence.events.__dict__ if evidence.events else None,
    }
