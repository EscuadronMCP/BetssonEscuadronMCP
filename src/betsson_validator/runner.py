"""Ejecuta un escenario de principio a fin: navegador → login → juego → tirada → informe.

Coordina las piezas sin contener lógica de negocio: la evaluación vive en scenarios/evaluation.
"""

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
from betsson_validator.perception.ocr import TextReader
from betsson_validator.providers.pragmatic.game import PragmaticGame, ScreenObservation
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
    MotionSummary,
    NetworkSummary,
    RunEvidence,
    ScreenSnapshot,
)

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


def run_scenario(
    scenario: Scenario,
    market: MarketConfig,
    provider: ProviderConfig,
    *,
    settings: BrowserSettings,
    reader: TextReader,
    out_dir: Path,
) -> ScenarioRun:
    plan = PLANS[scenario]
    evidence_dir = out_dir / scenario.value
    recorder_files = EvidenceRecorder(evidence_dir)
    started = datetime.now(UTC)
    secrets: tuple[str, ...] = ()
    results: tuple[CheckResult, ...] = ()
    error: str | None = None
    try:
        credentials = plan.account(market).resolve()
        secrets = (credentials.email.get_secret_value(), credentials.password.get_secret_value())
        with browser_context(settings, evidence_dir) as context:
            page = context.new_page()
            network = GameServiceRecorder(context)
            casino = BetssonCasino(page, market, typing_delay_ms=settings.slow_typing_ms)
            casino.open()
            casino.login(credentials)
            with tracing(context, evidence_dir / "trace.zip"):
                results = _play(
                    casino,
                    provider,
                    market=market,
                    plan=plan,
                    network=network,
                    files=recorder_files,
                    reader=reader,
                )
    except Exception as exception:  # el informe debe recoger cualquier fallo, sin secretos
        error = _sanitize(f"{type(exception).__name__}: {exception}", secrets)
    return ScenarioRun(
        scenario=scenario,
        market=market.id,
        provider=provider.filter_label,
        game=provider.game_slug,
        started_at=started,
        finished_at=datetime.now(UTC),
        results=results,
        error=error,
    )


def _play(
    casino: BetssonCasino,
    provider: ProviderConfig,
    *,
    market: MarketConfig,
    plan: ScenarioPlan,
    network: GameServiceRecorder,
    files: EvidenceRecorder,
    reader: TextReader,
) -> tuple[CheckResult, ...]:
    page = casino.page
    betsson_before = casino.read_balance()
    header_before = casino.capture_balance(files.directory / "00_saldo_betsson_antes.png")

    handle = casino.launch_game(provider)
    game = PragmaticGame(
        page,
        handle,
        profile=provider.screen,
        reader=reader,
        evidence=files,
        currency=market.currency,
    )
    game.wait_until_ready()
    ready = game.set_minimum_bet()
    bet = ready.hud.bet.money if ready.hud.bet else None
    if bet is None or bet.amount > provider.screen.max_bet:
        raise SafetyStopError(
            f"Apuesta mostrada {bet or 'no leída'}: supera el máximo de seguridad "
            f"{provider.screen.max_bet} o no se pudo leer. No se gira."
        )

    mark = network.mark()
    spin = game.spin_and_watch()
    after = game.observe("despues_de_girar")
    if plan.dismiss_message and after.message:
        game.dismiss_message()

    traffic = files.save_json("trafico_juego_sin_tokens", network.redacted_log())
    calls = network.calls
    summary = _network_summary(calls[:mark], calls[mark:], str(traffic))

    betsson_after = casino.read_balance_after(betsson_before)
    header_after = casino.capture_balance(files.directory / "99_saldo_betsson_despues.png")

    evidence = RunEvidence(
        market_currency=market.currency,
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
    }
