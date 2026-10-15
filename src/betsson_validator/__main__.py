"""Línea de comandos.

uv run python -m betsson_validator run --scenario all          # valida (sin IA si hay perfil)
uv run python -m betsson_validator learn --game big-bass-splash # incorpora un juego nuevo
"""

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from betsson_validator.browser import BrowserSettings
from betsson_validator.config.market import SameAccountError, load_market
from betsson_validator.config.provider import load_provider
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import Status
from betsson_validator.perception.learner import ClaudeScreenLearner, ScreenLearner
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.report.writer import (
    RunInfo,
    overall_status,
    render_markdown,
    write_report,
)
from betsson_validator.runner import RunContext, failed_run, run_scenario
from betsson_validator.scenarios.faults import BETSSON_BALANCE_DRIFT, DEMO_FAILURE
from betsson_validator.security import audit_and_quarantine, scrub_files, scrub_text


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
        "--no-demo-fault",
        action="store_true",
        help="No incluir la prueba que falla a propósito (por defecto se incluye y no cuenta).",
    )
    run.add_argument(
        "--ax-probe",
        action="store_true",
        help="Diagnóstico: guarda el árbol de accesibilidad del juego (no cambia veredictos).",
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
        ax_probe=getattr(args, "ax_probe", False),
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
    # La prueba que falla a propósito va en el escenario 1 si se pide (la regla del dinero).
    demo_target = None
    if not args.no_demo_fault and faulty is None:
        demo_target = (
            Scenario.COMPLETED_SPIN if Scenario.COMPLETED_SPIN in scenarios else scenarios[0]
        )
    runs = _run_all(scenarios, ctx, parallel=not args.sequential, faulty=faulty, demo=demo_target)
    for run in runs:
        print(
            f"{run.scenario.value}: {run.status.value}" + (f" ({run.error})" if run.error else "")
        )
        if run.injected_fault:
            print(f"  aviso: {run.injected_fault}")
        if run.demo is not None:
            found = "FAIL detectado (como se esperaba)" if run.demo.detected else "NO detectado"
            print(f"  prueba que falla a propósito: {found}; no cuenta en el resultado")
        for note in run.notes:
            print(f"  nota: {note}")
    info = RunInfo(
        code_version=_code_version(), requested=tuple(scenarios), run_id=os.getenv("GITHUB_RUN_ID")
    )
    try:
        json_path, html_path = write_report(runs, ctx.out_dir, info)
    except OSError as error:  # sin informe escrito no se anuncia ninguno
        print(f"No se pudo escribir el informe en {ctx.out_dir}: {type(error).__name__}")
        return _CONFIG_ERROR
    secrets = ctx.market.accounts.secrets()
    scrub_files((json_path, html_path), secrets)  # el informe se publica siempre: se limpia
    for leaked in audit_and_quarantine(ctx.out_dir, secrets):
        print(f"  evidencia retirada por contener secretos: {leaked}")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(scrub_text(render_markdown(runs, info, ctx.out_dir), secrets))
    print(f"Duración: {time.monotonic() - started:.0f} s\nInforme: {html_path}\nDatos: {json_path}")
    # El mismo veredicto global que el informe: un escenario pedido que falta también es FAIL.
    return 0 if overall_status(runs, info) is Status.PASS else 1


def _code_version() -> str:
    """SHA del código ejecutado: el de GitHub Actions o el del checkout local."""
    if sha := os.getenv("GITHUB_SHA"):
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git del sistema
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "desconocida"
    return result.stdout.strip() or "desconocida"


def _run_all(
    scenarios: list[Scenario],
    ctx: RunContext,
    *,
    parallel: bool,
    faulty: Scenario | None,
    demo: Scenario | None = None,
) -> list[ScenarioRun]:
    """Cada escenario usa su propia cuenta, así que pueden ir a la vez: el tiempo total es el del
    más lento. Cada hilo tiene su navegador y su lector de OCR (no se comparten entre hilos)."""

    def context_for(scenario: Scenario, reader: RapidOcrReader | None = None) -> RunContext:
        fault = BETSSON_BALANCE_DRIFT if scenario is faulty else None
        demo_fault = DEMO_FAILURE if scenario is demo else None
        return replace(ctx, reader=reader or ctx.reader, fault=fault, demo_fault=demo_fault)

    if not parallel or len(scenarios) == 1:
        return [run_scenario(scenario, context_for(scenario)) for scenario in scenarios]
    with ThreadPoolExecutor(max_workers=len(scenarios)) as pool:
        futures = {
            scenario: pool.submit(run_scenario, scenario, context_for(scenario, RapidOcrReader()))
            for scenario in scenarios
        }
        runs = []
        for scenario, future in futures.items():
            try:
                runs.append(future.result())
            except Exception as error:  # un fallo inesperado de un hilo es un FAIL, no un cierre
                runs.append(failed_run(scenario, ctx, error))
        return runs


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


_CONFIG_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    load_dotenv()
    # Con el PID: dos ejecuciones lanzadas en el mismo segundo no comparten carpeta.
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir: Path = args.out or Path("reports") / f"{stamp}-{os.getpid()}-{args.command}"
    try:
        ctx = _context(args, out_dir)
    except (ValueError, OSError, yaml.YAMLError) as error:  # incluye la validación de pydantic
        first_line = str(error).splitlines()[0] if str(error) else type(error).__name__
        print(f"Configuración no válida: {first_line}")
        return _CONFIG_ERROR
    return _run(args, ctx) if args.command == "run" else _learn(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
