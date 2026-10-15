"""Ejecuta un escenario de principio a fin: navegador → login → juego → tirada → informe.

Coordina las piezas sin contener lógica de negocio: la evaluación vive en scenarios/evaluation,
las condiciones previas al giro en scenarios/preconditions y los testigos de cada proveedor en
providers/registry (el ejecutor no conoce a ningún proveedor concreto).
"""

import re
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Frame

from betsson_validator.browser import BrowserSettings, browser_context, tracing
from betsson_validator.casino.betsson import GAME_FRAME_SELECTOR, BetssonCasino
from betsson_validator.config.market import AccountEnv, MarketConfig
from betsson_validator.config.provider import ProviderConfig
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import detect_currency
from betsson_validator.domain.run import DemoFailure, ScenarioRun
from betsson_validator.domain.verdict import CheckResult, Status, withdraw_evidence
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game import accessibility
from betsson_validator.game.events import (
    GameEventRecorder,
    authorized_events,
    capture_anomalies,
    payloads,
)
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
    require_known_minimum,
    require_no_funds,
)
from betsson_validator.security import audit_and_quarantine, scrub_text, scrub_trace
from betsson_validator.timeline import StageClock

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
    # Diagnóstico opcional: árbol de accesibilidad del juego antes y después de girar.
    ax_probe: bool = False
    # Prueba que falla a propósito, evaluada aparte sobre lo observado (no cuenta).
    demo_fault: InjectedFault | None = None


def run_scenario(scenario: Scenario, ctx: RunContext) -> ScenarioRun:
    plan = PLANS[scenario]
    evidence_dir = ctx.out_dir / scenario.value
    files = EvidenceRecorder(evidence_dir)
    started = datetime.now(UTC)
    secrets: tuple[str, ...] = ()
    results: tuple[CheckResult, ...] = ()
    notes: list[str] = []
    error: str | None = None
    demo: DemoFailure | None = None
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
            clock = StageClock()
            casino.open()
            clock.mark("web abierta")
            casino.login(credentials)
            clock.mark("sesión iniciada")
            model = ScreenModel(
                profile=profile,
                reader=ctx.reader,
                currency=ctx.market.currency,
                learner=ctx.learner,
                win_candidates=ctx.market.ui.win_label_candidates,
            )
            with tracing(context, evidence_dir / "trace.zip"):
                try:
                    results, demo = _play(
                        casino,
                        ctx,
                        plan=plan,
                        model=model,
                        witnesses=_Witnesses(network, interpreter),
                        files=files,
                        clock=clock,
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
        demo=demo,
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
    # Orígenes del árbol de marcos del juego con el juego listo: los únicos autorizados a
    # enviar eventos (si el marco navega después a otro origen, sus mensajes no cuentan).
    game_origins: frozenset[str]


def _prepare(
    casino: BetssonCasino,
    ctx: RunContext,
    *,
    plan: ScenarioPlan,
    model: ScreenModel,
    witnesses: _Witnesses,
    files: EvidenceRecorder,
    clock: StageClock,
) -> _Ready:
    """Hasta justo antes de girar: saldo, juego cargado, apuesta mínima y condiciones previas."""
    betsson_before = casino.read_balance()
    header_before = casino.capture_balance(files.directory / "00_saldo_betsson_antes.jpg")
    clock.mark("saldo inicial leído")
    handle = casino.launch_game(ctx.provider, ctx.game)
    clock.mark("juego abierto")
    game_frame = _game_frame(casino)
    if witnesses.network is not None and game_frame is not None:
        witnesses.network.bind(game_frame)
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
    clock.mark("juego listo con apuesta mínima")
    seen = _snapshot(ready)
    bet = check_bet(seen.bet, ctx.provider.max_bet, ctx.market.currency, seen.currencies_seen)
    require_known_minimum(bet, model.profile.min_bet)
    plan.precondition(betsson_before, seen.credit, bet)
    origins = _frame_origins(game_frame) if game_frame is not None else frozenset()
    return _Ready(betsson_before, header_before, game, ready, origins)


def _play(
    casino: BetssonCasino,
    ctx: RunContext,
    *,
    plan: ScenarioPlan,
    model: ScreenModel,
    witnesses: _Witnesses,
    files: EvidenceRecorder,
    clock: StageClock,
) -> tuple[tuple[CheckResult, ...], DemoFailure | None]:
    ready = _prepare(
        casino, ctx, plan=plan, model=model, witnesses=witnesses, files=files, clock=clock
    )
    game = ready.game
    game_frame = casino.page.frame_locator(GAME_FRAME_SELECTOR)
    probes = [accessibility.probe(game_frame, "antes_de_girar")] if ctx.ax_probe else []
    mark = witnesses.network.mark() if witnesses.network else 0
    events_mark = len(GameEventRecorder.collect(casino.page)) if witnesses.events else 0
    spin = game.spin_and_watch()
    clock.mark("giro observado")
    if _wait_round_closed(casino, witnesses, mark, events_mark) is False:
        model.notes.append(
            f"La ronda no se cerró en {_ROUND_CLOSE_TIMEOUT_S} s según el servidor y los "
            "eventos del juego: se leyó el estado final igualmente."
        )
    clock.mark("ronda cerrada")
    after = game.observe_settled("despues_de_girar")
    clock.mark("marcador estable")
    if ctx.ax_probe:  # con el mensaje del juego aún visible en el escenario 2
        probes.append(accessibility.probe(game_frame, "despues_de_girar"))
        files.save_json("accesibilidad", [asdict(item) for item in probes])
    # Los eventos se leen ANTES de salir de la página del juego.
    events_summary = _events_summary(casino, witnesses.events, ready, events_mark, files)
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
    clock.mark("saldo final de Betsson")
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
    summary_data["stages"] = clock.stages
    summary_data["profile"] = {
        "learned_with": model.profile.learned_with,
        "learned_at": model.profile.learned_at,
    }
    if ctx.fault is not None:
        summary_data["injected_fault"] = ctx.fault.description
        evidence = ctx.fault.apply(evidence)
    files.save_json("resumen_observado", summary_data)
    return plan.evaluator(evidence), _demo_failure(plan, evidence, ctx.demo_fault)


def _demo_failure(
    plan: ScenarioPlan, evidence: RunEvidence, fault: InjectedFault | None
) -> DemoFailure | None:
    """Evalúa aparte lo observado con el fallo inyectado; solo se muestran los FAIL."""
    if fault is None:
        return None
    failing = tuple(
        result for result in plan.evaluator(fault.apply(evidence)) if result.status is Status.FAIL
    )
    return DemoFailure(description=fault.description, results=failing)


def _events_summary(
    casino: BetssonCasino,
    interpreter: EventsInterpreter | None,
    ready: _Ready,
    events_mark: int,
    files: EvidenceRecorder,
) -> GameEventsSummary | None:
    """Eventos del juego durante la tirada, solo de sus orígenes, con las anomalías de captura."""
    if interpreter is None:
        return None
    captured = GameEventRecorder.collect(casino.page)[events_mark:]
    game_events, foreign = authorized_events(captured, ready.game_origins)
    events_file = files.save_json("eventos_del_juego", captured)
    summary = interpreter.summarize(payloads(game_events), str(events_file))
    problems = capture_anomalies(game_events, GameEventRecorder.dropped(casino.page))
    if foreign:
        origins = ", ".join(sorted({str(e.get("origin")) for e in foreign}))
        problems = (*problems, f"{len(foreign)} eventos de un origen no autorizado ({origins})")
    if problems:
        summary = replace(summary, anomalies=(*summary.anomalies, *problems))
    return summary


def _game_frame(casino: BetssonCasino) -> Frame | None:
    """Marco del juego según el navegador (el iframe del lanzador de Betsson)."""
    try:
        element = casino.page.locator(GAME_FRAME_SELECTOR).element_handle(timeout=5_000)
        return element.content_frame() if element else None
    except PlaywrightError:
        return None


def _frame_origins(frame: Frame) -> frozenset[str]:
    """Orígenes web del marco y de todos sus descendientes."""
    origins: set[str] = set()
    pending = [frame]
    while pending:
        current = pending.pop()
        parts = urlsplit(current.url)
        if parts.scheme in {"http", "https"}:
            origins.add(f"{parts.scheme}://{parts.netloc}")
        pending.extend(current.child_frames)
    return frozenset(origins)


_ROUND_CLOSE_TIMEOUT_S = 30


def _wait_round_closed(
    casino: BetssonCasino, witnesses: _Witnesses, mark: int, events_mark: int
) -> bool | None:
    """Espera a que el servidor y los eventos den la ronda por cerrada (cascadas, cobro del
    premio) antes de la lectura final. Solo orienta CUÁNDO leer: la prueba sigue siendo lo que
    ve el jugador. None si no hay testigos que lo indiquen; False si se agotó la espera."""
    if witnesses.network is None and witnesses.events is None:
        return None
    deadline = time.monotonic() + _ROUND_CLOSE_TIMEOUT_S
    while True:
        open_round = False
        if witnesses.events is not None:
            recorded = payloads(GameEventRecorder.collect(casino.page)[events_mark:])
            summary = witnesses.events.summarize(recorded, "")
            open_round |= summary.round_started and not summary.round_ended
        if witnesses.network is not None:
            network = witnesses.network.summarize(mark, "")
            open_round |= network.wager_accepted is not None and not network.settled
        if not open_round:
            return True
        if time.monotonic() > deadline:
            return False
        casino.page.wait_for_timeout(500)


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
