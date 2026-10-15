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
    assert markdown.splitlines()[0] == "## ❌ Validación de juegos: FAIL"
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


def test_a_duplicated_pass_cannot_hide_a_fail() -> None:
    failed = evaluate(
        Check.WAGER_MATCHES.value,
        (
            Testimony(
                witness="pantalla",
                kind=WitnessKind.VISUAL,
                outcome=Outcome.CONTRADICTS,
                detail="mal",
            ),
        ),
    )
    passed = confirmed(Check.WAGER_MATCHES)
    assert run_with((*all_checks_pass(), failed)).status is Status.FAIL
    assert run_with((failed, *all_checks_pass())).status is Status.FAIL
    assert run_with((*all_checks_pass(), passed)).status is Status.PASS


def test_evidence_links_use_posix_urls_and_flag_missing_files(tmp_path: Path) -> None:
    folder = tmp_path / "completed_spin"
    folder.mkdir()
    (folder / "01_juego.jpg").write_bytes(b"jpg")
    kept, removed = folder / "01_juego.jpg", folder / "02_retirada.jpg"
    screen = Testimony(
        witness="pantalla",
        kind=WitnessKind.VISUAL,
        outcome=Outcome.CONFIRMS,
        detail="ok",
        evidence=(str(kept), str(removed)),
    )
    result = evaluate(Check.SPIN_COMPLETED.value, (screen,))
    _, html_path = write_report([run_with((result,))], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert 'src="completed_spin/01_juego.jpg"' in html
    assert "02_retirada.jpg: no disponible" in html
    assert "\\\\" not in html


# --- Auditoría R02: procedencia, alcance y enlaces ---------------------------------------------


def test_report_identifies_code_version_and_partial_scope(tmp_path: Path) -> None:
    from betsson_validator.report.writer import RunInfo  # noqa: PLC0415

    info = RunInfo(code_version="3572172abcdef0123", requested=(Scenario.COMPLETED_SPIN,))
    json_path, html_path = write_report([run_with(all_checks_pass())], tmp_path, info)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["code_version"] == "3572172abcdef0123"
    assert data["partial_scope"] is True
    assert "alcance parcial" in html_path.read_text(encoding="utf-8")
    assert "alcance parcial" in render_markdown([run_with(all_checks_pass())], info)


def test_a_requested_scenario_that_did_not_run_is_not_a_global_pass(tmp_path: Path) -> None:
    from betsson_validator.report.writer import RunInfo  # noqa: PLC0415

    info = RunInfo(requested=tuple(Scenario))
    json_path, _ = write_report([run_with(all_checks_pass())], tmp_path, info)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "FAIL"


def test_links_with_spaces_hash_and_accents_are_encoded(tmp_path: Path) -> None:
    folder = tmp_path / "completed_spin"
    folder.mkdir()
    picture = folder / "captura #1 señal.jpg"
    picture.write_bytes(b"jpg")
    screen = Testimony(
        witness="pantalla",
        kind=WitnessKind.VISUAL,
        outcome=Outcome.CONFIRMS,
        detail="ok",
        evidence=(str(picture),),
    )
    result = evaluate(Check.SPIN_COMPLETED.value, (screen,))
    _, html_path = write_report([run_with((result,))], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert 'src="completed_spin/captura%20%231%20se%C3%B1al.jpg"' in html


def test_failure_screenshot_is_linked_next_to_the_error(tmp_path: Path) -> None:
    folder = tmp_path / "completed_spin"
    folder.mkdir()
    (folder / "fallo_pantalla.jpg").write_bytes(b"jpg")
    _, html_path = write_report([run_with((), error="CasinoError: no aparece")], tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert 'href="completed_spin/fallo_pantalla.jpg"' in html
    assert "Captura de la pantalla al fallar" in html
