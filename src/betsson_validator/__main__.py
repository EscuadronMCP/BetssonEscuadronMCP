"""Línea de comandos.

uv run python -m betsson_validator run --scenario all          # valida (sin IA si hay perfil)
uv run python -m betsson_validator learn --game big-bass-splash # incorpora un juego nuevo
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from betsson_validator.browser import BrowserSettings
from betsson_validator.config.market import load_market
from betsson_validator.config.provider import load_provider
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.verdict import Status
from betsson_validator.perception.learner import ClaudeScreenLearner, ScreenLearner
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.report.writer import render_markdown, write_report
from betsson_validator.runner import RunContext, run_scenario


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
    return parser.parse_args(argv)


def _context(args: argparse.Namespace, out_dir: Path) -> RunContext:
    provider = load_provider(args.provider)
    learner: ScreenLearner | None = (
        ClaudeScreenLearner() if os.getenv("ANTHROPIC_API_KEY") else None
    )
    return RunContext(
        market=load_market(args.market),
        provider=provider,
        game=args.game or provider.game_slug,
        settings=BrowserSettings(
            headless=not args.headed, channel=None if args.channel == "chromium" else args.channel
        ),
        reader=RapidOcrReader(),
        out_dir=out_dir,
        learner=learner,
    )


def _run(args: argparse.Namespace, ctx: RunContext) -> int:
    scenarios = list(Scenario) if args.scenario == "all" else [Scenario(args.scenario)]
    if ctx.learner is None:
        print("Sin ANTHROPIC_API_KEY: se usa el perfil aprendido sin posibilidad de reaprender.")
    runs = []
    for scenario in scenarios:
        print(f"→ {scenario.value} · {ctx.market.id} · {ctx.provider.filter_label} · {ctx.game}")
        run = run_scenario(scenario, ctx)
        print(f"  {run.status.value}" + (f" ({run.error})" if run.error else ""), flush=True)
        for note in run.notes:
            print(f"  nota: {note}")
        runs.append(run)
    json_path, html_path = write_report(runs, ctx.out_dir)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(render_markdown(runs))
    print(f"Informe: {html_path}\nDatos: {json_path}")
    return 0 if all(run.status is Status.PASS for run in runs) else 1


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
