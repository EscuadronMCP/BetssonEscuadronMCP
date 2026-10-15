"""El informe muestra toda la información observada de forma gráfica (petición del jurado)."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from betsson_validator.domain.checks import Scenario
from betsson_validator.report.observed import load_observed
from betsson_validator.report.sections import events_timeline, motion_section, observed_values

OBSERVED: dict[str, Any] = {
    "betsson_before": "193.21 EUR",
    "betsson_after": "193.01 EUR",
    "screen_before": {"credit": "193.21 EUR", "bet": "0.20 EUR", "currencies_seen": ["EUR"]},
    "screen_after": {"credit": "193.01 EUR", "bet": "0.20 EUR", "win": None},
    "network": {
        "wager_accepted": "0.20",
        "declared_win": "0.00",
        "balance_before": "193.21",
        "balance_after": "193.01",
    },
    "events": {"bet": "0.2", "win": "0", "balance_before": "193.21", "balance_after": "193.01"},
    "motion_scores": [0.0, 0.04, 0.22, 0.25, 0.15, 0.19, 0.28, 0.17, 0.03, 0.0, 0.0, 0.0, 0.0],
    "motion_thresholds": {
        "start": 0.08,
        "still": 0.01,
        "still_samples": 4,
        "min_active_samples": 3,
        "relative_still": 0.1,
    },
}


def write(
    folder: Path, data: Mapping[str, Any], events: Sequence[Mapping[str, Any]] | None = None
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "resumen_observado.json").write_text(json.dumps(data), encoding="utf-8")
    if events is not None:
        (folder / "eventos_del_juego.json").write_text(json.dumps(list(events)), encoding="utf-8")


def test_money_rule_and_values_of_every_witness_are_shown(tmp_path: Path) -> None:
    write(tmp_path, OBSERVED)
    observed = load_observed(tmp_path)
    assert observed is not None
    html = observed_values(observed, Scenario.COMPLETED_SPIN)
    assert "193,21 €" in html and "193,01 €" in html
    assert "Betsson muestra 193,01 €" in html
    assert "✓ coinciden" in html


def test_a_witness_that_disagrees_is_flagged(tmp_path: Path) -> None:
    data = {**OBSERVED, "network": {**OBSERVED["network"], "balance_after": "192.91"}}
    write(tmp_path, data)
    observed = load_observed(tmp_path)
    assert observed is not None
    assert "✗ discrepancia" in observed_values(observed, Scenario.COMPLETED_SPIN)


def test_motion_chart_and_event_timeline_are_drawn(tmp_path: Path) -> None:
    events = [
        {"seq": 0, "t": 1000, "data": {"name": "gameRoundStarted", "betAmount": 0.2}},
        {"seq": 1, "t": 2900, "data": {"name": "gameRoundEnded", "winAmount": 0}},
    ]
    write(tmp_path, OBSERVED, events)
    observed = load_observed(tmp_path)
    assert observed is not None
    chart = motion_section(observed)
    assert "<svg" in chart and "inicio" in chart and "fin" in chart
    timeline = events_timeline(observed)
    assert "gameRoundEnded" in timeline and "+1.9 s" in timeline


def test_the_insufficient_funds_message_is_highlighted(tmp_path: Path) -> None:
    data = {
        **OBSERVED,
        "betsson_after": "193.21 EUR",
        "screen_after": {"credit": "0.00 EUR", "message": "Fondos insuficientes para apostar"},
        "events": {"languages": ["es"]},
    }
    write(tmp_path, data)
    observed = load_observed(tmp_path)
    assert observed is not None
    html = observed_values(observed, Scenario.INSUFFICIENT_BALANCE)
    assert "«Fondos insuficientes para apostar»" in html
    assert "idioma comunicado por el juego: es" in html


def test_missing_or_broken_files_do_not_break_the_report(tmp_path: Path) -> None:
    assert load_observed(tmp_path) is None
    (tmp_path / "resumen_observado.json").write_text("{roto", encoding="utf-8")
    assert load_observed(tmp_path) is None


def test_stage_timeline_and_plain_story_are_written(tmp_path: Path) -> None:
    from betsson_validator.report.sections import narrative, stages_timeline  # noqa: PLC0415

    data = {
        **OBSERVED,
        "motion": {"completed": True},
        "stages": [{"name": "sesión iniciada", "s": 9.5}, {"name": "giro observado", "s": 50.0}],
    }
    write(tmp_path, data)
    observed = load_observed(tmp_path)
    assert observed is not None
    timeline = stages_timeline(observed)
    assert "sesión iniciada" in timeline and "40.5 s" in timeline
    story = narrative(observed, Scenario.COMPLETED_SPIN, "sweet-bonanza-2500")
    assert "Se apostaron 0,20 €" in story
    assert "cuadra con la regla del reto" in story


def test_actions_summary_tells_what_happened(tmp_path: Path) -> None:
    from datetime import UTC, datetime  # noqa: PLC0415

    from betsson_validator.domain.run import ScenarioRun  # noqa: PLC0415
    from betsson_validator.report.writer import render_markdown  # noqa: PLC0415

    write(tmp_path / "completed_spin", {**OBSERVED, "motion": {"completed": True}})
    now = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
    run = ScenarioRun(
        scenario=Scenario.COMPLETED_SPIN,
        market="es",
        provider="Pragmatic Play",
        game="sweet-bonanza-2500",
        started_at=now,
        finished_at=now,
        results=(),
    )
    markdown = render_markdown([run], out_dir=tmp_path)
    assert "Se apostaron 0,20 €" in markdown
    assert "comprobaciones superadas" in markdown


def test_the_story_never_claims_what_was_not_read(tmp_path: Path) -> None:
    """Sin datos no se afirma «ningún saldo cambió» ni «no hubo premio»."""
    from betsson_validator.report.sections import narrative  # noqa: PLC0415

    write(tmp_path / "a", {"screen_after": {"message": "Fondos insuficientes"}})
    blind = load_observed(tmp_path / "a")
    assert blind is not None
    story = narrative(blind, Scenario.INSUFFICIENT_BALANCE, "juego")
    assert "No se pudieron leer todos los saldos" in story
    assert "Ningún saldo cambió" not in story

    write(tmp_path / "b", {**OBSERVED, "motion": {"completed": True}})
    no_win = load_observed(tmp_path / "b")
    assert no_win is not None
    story = narrative(no_win, Scenario.COMPLETED_SPIN, "juego")
    assert "no se vio premio en pantalla" in story
    assert "no hubo premio" not in story
