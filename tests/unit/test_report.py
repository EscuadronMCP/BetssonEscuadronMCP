import json
from datetime import UTC, datetime
from pathlib import Path

from betsson_validator.domain.checks import SCENARIO_CHECKS, Check, Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import (
    CheckResult,
    Outcome,
    Status,
    Testimony,
    WitnessKind,
    evaluate,
)
from betsson_validator.report.writer import render_markdown, write_report

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def confirmed(check: Check, detail: str = "ok") -> CheckResult:
    screen = Testimony(
        witness="pantalla", kind=WitnessKind.VISUAL, outcome=Outcome.CONFIRMS, detail=detail
    )
    return evaluate(check.value, (screen,))


def run_with(results: tuple[CheckResult, ...], error: str | None = None) -> ScenarioRun:
    return ScenarioRun(
        scenario=Scenario.COMPLETED_SPIN,
        market="es",
        provider="PragmaticPlay",
        game="Juego",
        started_at=NOW,
        finished_at=NOW,
        results=results,
        error=error,
    )


def all_checks_pass() -> tuple[CheckResult, ...]:
    return tuple(confirmed(c) for c in SCENARIO_CHECKS[Scenario.COMPLETED_SPIN])


def test_run_passes_only_when_every_check_passes() -> None:
    assert run_with(all_checks_pass()).status is Status.PASS


def test_missing_check_fails_the_run() -> None:
    run = run_with(all_checks_pass()[:-1])
    assert run.status is Status.FAIL
    assert run.missing_checks() == (Check.BETSSON_BALANCE_RECONCILES,)


def test_error_fails_the_run() -> None:
    assert run_with(all_checks_pass(), error="timeout").status is Status.FAIL


def test_report_writes_json_and_html(tmp_path: Path) -> None:
    json_path, html_path = write_report([run_with(all_checks_pass())], tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"
    assert data["runs"][0]["status"] == "PASS"
    assert "Escenario 1" in html_path.read_text(encoding="utf-8")


def test_report_escapes_untrusted_text(tmp_path: Path) -> None:
    results = (confirmed(Check.SPIN_COMPLETED, detail="<script>alert(1)</script>"),)
    _, html_path = write_report([run_with(results)], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_report_lists_unevaluated_checks(tmp_path: Path) -> None:
    _, html_path = write_report([run_with(())], tmp_path)
    assert "No se llegó a evaluar" in html_path.read_text(encoding="utf-8")


def test_markdown_summary_lists_every_check() -> None:

    markdown = render_markdown([run_with(all_checks_pass()[:-1])])
    assert markdown.startswith("## Validación de juegos: FAIL")
    assert markdown.count("| PASS |") == 4
    assert "No evaluada" in markdown


def test_report_links_full_evidence(tmp_path: Path) -> None:
    folder = tmp_path / "completed_spin"
    (folder / "video").mkdir(parents=True)
    (folder / "video" / "run.webm").write_bytes(b"video")
    (folder / "eventos_del_juego.json").write_text("[]")
    _, html_path = write_report([run_with(all_checks_pass())], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert 'href="completed_spin/video/run.webm"' in html
    assert "Eventos del juego" in html


def test_report_starts_with_a_plain_language_summary(tmp_path: Path) -> None:
    _, html_path = write_report([run_with(all_checks_pass()[:-1])], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert "4 de 5 comprobaciones superadas" in html
    assert "testigos independientes" in html
