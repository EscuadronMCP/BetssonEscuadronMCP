"""Línea de comandos: `uv run python -m betsson_validator --scenario all`."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from betsson_validator.browser import BrowserSettings
from betsson_validator.config.market import load_market
from betsson_validator.config.provider import load_provider
from betsson_validator.domain.checks import Scenario
from betsson_validator.domain.verdict import Status
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.report.writer import write_report
from betsson_validator.runner import run_scenario


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="betsson_validator",
        description="Valida un juego de casino en Betsson como lo vería un jugador.",
    )
    parser.add_argument(
        "--scenario",
        choices=[*[s.value for s in Scenario], "all"],
        default="all",
        help="Escenario a ejecutar (por defecto, ambos).",
    )
    parser.add_argument("--market", default="es", help="Mercado (config/markets/<id>.yaml).")
    parser.add_argument(
        "--provider", default="pragmaticplay", help="Proveedor (config/providers/<id>.yaml)."
    )
    parser.add_argument("--out", type=Path, default=None, help="Carpeta del informe.")
    parser.add_argument("--headed", action="store_true", help="Mostrar el navegador.")
    parser.add_argument(
        "--channel", default="chrome", help="Canal del navegador ('chrome' o 'chromium')."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    load_dotenv()
    market = load_market(args.market)
    provider = load_provider(args.provider)
    scenarios = list(Scenario) if args.scenario == "all" else [Scenario(args.scenario)]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir: Path = args.out or Path("reports") / f"{stamp}-{market.id}"
    settings = BrowserSettings(
        headless=not args.headed, channel=None if args.channel == "chromium" else args.channel
    )
    reader = RapidOcrReader()
    runs = []
    for scenario in scenarios:
        print(f"→ {scenario.value} en {market.id} con {provider.filter_label}…", flush=True)
        run = run_scenario(
            scenario, market, provider, settings=settings, reader=reader, out_dir=out_dir
        )
        print(f"  {run.status.value}" + (f" ({run.error})" if run.error else ""), flush=True)
        runs.append(run)
    json_path, html_path = write_report(runs, out_dir)
    print(f"Informe: {html_path}\nDatos: {json_path}")
    return 0 if all(run.status is Status.PASS for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
