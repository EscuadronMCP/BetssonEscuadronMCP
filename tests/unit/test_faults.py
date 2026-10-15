"""El fallo intencionado de la demostración se detecta como FAIL por discrepancia y se anuncia."""

from datetime import UTC, datetime
from pathlib import Path

from betsson_validator.domain.checks import Check, Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import Status
from betsson_validator.report.writer import render_markdown, write_report
from betsson_validator.scenarios.evaluation import (
    evaluate_completed_spin,
    evaluate_insufficient_balance,
)
from betsson_validator.scenarios.faults import BETSSON_BALANCE_DRIFT
from tests.unit.test_evaluation import REJECTED_SPIN, WINNING_SPIN, statuses


def test_drifted_betsson_balance_fails_the_money_rule() -> None:
    result = statuses(evaluate_completed_spin(BETSSON_BALANCE_DRIFT.apply(WINNING_SPIN)))
    assert result[Check.BETSSON_BALANCE_RECONCILES.value] is Status.FAIL
    assert result[Check.SPIN_COMPLETED.value] is Status.PASS


def test_drifted_betsson_balance_fails_the_rejected_spin() -> None:
    result = statuses(evaluate_insufficient_balance(BETSSON_BALANCE_DRIFT.apply(REJECTED_SPIN)))
    assert result[Check.BETSSON_BALANCE_UNCHANGED.value] is Status.FAIL
    assert result[Check.SPIN_REJECTED.value] is Status.PASS


def test_report_announces_the_intentional_fault(tmp_path: Path) -> None:
    now = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
    run = ScenarioRun(
        scenario=Scenario.INSUFFICIENT_BALANCE,
        market="es",
        provider="Pragmatic Play",
        game="sweet-bonanza-2500",
        started_at=now,
        finished_at=now,
        results=evaluate_insufficient_balance(BETSSON_BALANCE_DRIFT.apply(REJECTED_SPIN)),
        injected_fault=BETSSON_BALANCE_DRIFT.description,
    )
    assert run.status is Status.FAIL
    _, html_path = write_report([run], tmp_path)
    assert "FALLO INTENCIONADO" in html_path.read_text(encoding="utf-8")
    assert "FALLO INTENCIONADO" in render_markdown([run])
