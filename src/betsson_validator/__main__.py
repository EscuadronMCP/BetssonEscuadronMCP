"""Línea de comandos.

uv run python -m betsson_validator run --scenario all          # valida (sin IA si hay perfil)
uv run python -m betsson_validator learn --game big-bass-splash # incorpora un juego nuevo
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from betsson_validator.browser import BrowserSettings
from betsson_validator.config.market import SameAccountError, load_market
from betsson_validator.config.provider import load_provider
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import Status
from betsson_validator.perception.learner import ClaudeScreenLearner, ScreenLearner
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.report.writer import render_markdown, write_report
from betsson_validator.runner import RunContext, run_scenario
from betsson_validator.scenarios.faults import BETSSON_BALANCE_DRIFT
from betsson_validator.security import audit_and_quarantine, scrub_files


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="betsson_validator",
        description="Valida juegos de casino en Betsson como los vería un jugador.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("run", "Ejecuta los escenarios y genera el informe."),
        ("learn", "Aprende el perfil de pantalla de un juego nuevo (no gira)."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--market", default="es", help="config/markets/<id>.yaml")
        command.add_argument(
            "--provider", default="pragmaticplay", help="config/providers/<id>.yaml"
        )
        command.add_argument(
            "--game", default=None, help="Juego (slug). Por defecto, el del proveedor."
        )
        command.add_argument("--out", type=Path, default=None, help="Carpeta de salida.")
        command.add_argument("--headed", action="store_true", help="Mostrar el navegador.")
        command.add_argument("--channel", default="chrome", help="'chrome' o 'chromium'.")
    run = commands.choices["run"]
    run.add_argument("--scenario", choices=[*[s.value for s in Scenario], "all"], default="all")
    run.add_argument("--summary", type=Path, default=None, help="Añade un resumen Markdown aquí.")
    run.add_argument("--video", action="store_true", help="Grabar vídeo (informe más pesado).")
    run.add_argument(
        "--inject-fault",
        choices=[s.value for s in Scenario],
        default=None,
        help="Demostración: provoca a propósito un fallo de saldo en ese escenario.",
    )
    run.add_argument(
        "--sequential",
        action="store_true",
        help="Ejecutar los escenarios uno tras otro (por defecto, en paralelo).",
    )
    return parser.parse_args(argv)


def _context(args: argparse.Namespace, out_dir: Path) -> RunContext:
    provider = load_provider(args.provider)
    market = load_market(args.market)
    learner: ScreenLearner | None = (
        ClaudeScreenLearner() if os.getenv("ANTHROPIC_API_KEY") else None
    )
    return RunContext(
        market=market,
        provider=provider,
        game=args.game or provider.game_slug,
        settings=BrowserSettings(
            headless=not args.headed,
            channel=None if args.channel == "chromium" else args.channel,
            record_video=getattr(args, "video", False),
            locale=market.locale,
            timezone=market.timezone,
        ),
        reader=RapidOcrReader(),
        out_dir=out_dir,
        learner=learner,
    )


def _run(args: argparse.Namespace, ctx: RunContext) -> int:
    scenarios = list(Scenario) if args.scenario == "all" else [Scenario(args.scenario)]
    try:
        ctx.market.accounts.ensure_distinct()
    except SameAccountError as error:
        print(f"No se ejecuta: {error}")
        return 1
    if ctx.learner is None:
        print("Sin ANTHROPIC_API_KEY: se usa el perfil aprendido sin posibilidad de reaprender.")
    for scenario in scenarios:
        print(f"→ {scenario.value} · {ctx.market.id} · {ctx.provider.filter_label} · {ctx.game}")
    started = time.monotonic()
    faulty = Scenario(args.inject_fault) if args.inject_fault else None
    runs = _run_all(scenarios, ctx, parallel=not args.sequential, faulty=faulty)
    for run in runs:
        print(
            f"{run.scenario.value}: {run.status.value}" + (f" ({run.error})" if run.error else "")
        )
        if run.injected_fault:
            print(f"  aviso: {run.injected_fault}")
        for note in run.notes:
            print(f"  nota: {note}")
    json_path, html_path = write_report(runs, ctx.out_dir)
    secrets = ctx.market.accounts.secrets()
    scrub_files((json_path, html_path), secrets)  # el informe se publica siempre: se limpia
    for leaked in audit_and_quarantine(ctx.out_dir, secrets):
        print(f"  evidencia retirada por contener secretos: {leaked}")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(render_markdown(runs))
    print(f"Duración: {time.monotonic() - started:.0f} s\nInforme: {html_path}\nDatos: {json_path}")
    return 0 if all(run.status is Status.PASS for run in runs) else 1


def _run_all(
    scenarios: list[Scenario], ctx: RunContext, *, parallel: bool, faulty: Scenario | None
) -> list[ScenarioRun]:
    """Cada escenario usa su propia cuenta, así que pueden ir a la vez: el tiempo total es el del
    más lento. Cada hilo tiene su navegador y su lector de OCR (no se comparten entre hilos)."""

    def context_for(scenario: Scenario, reader: RapidOcrReader | None = None) -> RunContext:
        fault = BETSSON_BALANCE_DRIFT if scenario is faulty else None
        return replace(ctx, reader=reader or ctx.reader, fault=fault)

    if not parallel or len(scenarios) == 1:
        return [run_scenario(scenario, context_for(scenario)) for scenario in scenarios]
    with ThreadPoolExecutor(max_workers=len(scenarios)) as pool:
        futures = [
            pool.submit(run_scenario, scenario, context_for(scenario, RapidOcrReader()))
            for scenario in scenarios
        ]
        return [future.result() for future in futures]


def _learn(ctx: RunContext) -> int:
    from betsson_validator.learning import LearningError, learn_game  # noqa: PLC0415

    try:
        result = learn_game(ctx)
    except LearningError as error:
        print(f"No se pudo aprender el juego: {error}")
        return 1
    print(f"Perfil guardado en {result.profile_path} (modelo {result.model}).")
    print(f"Coste de IA del aprendizaje: {result.ai_cost_usd:.4f} $")
    for check in result.checks:
        print(f"  ✓ {check}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    load_dotenv()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir: Path = args.out or Path("reports") / f"{stamp}-{args.command}"
    ctx = _context(args, out_dir)
    return _run(args, ctx) if args.command == "run" else _learn(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
