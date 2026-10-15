"""La línea de comandos falla de forma clara ante configuración inválida (auditoría R02)."""

from pathlib import Path

import pytest

from betsson_validator import __main__ as cli
from betsson_validator.__main__ import main


@pytest.fixture(autouse=True)
def _no_real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los tests no cargan el .env real: nunca hay credenciales en un test sin red."""
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)


def test_unknown_market_is_a_clear_configuration_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--market", "no-existe", "--out", "reports/no-se-crea"]) == 2
    out = capsys.readouterr().out
    assert "Configuración no válida" in out
    assert "Traceback" not in out
    assert not Path("reports/no-se-crea").exists()


def test_unknown_provider_is_a_clear_configuration_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["learn", "--provider", "no-existe"]) == 2
    assert "Proveedor desconocido" in capsys.readouterr().out


def test_cli_missing_requested_scenario_has_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Auditoría R03-11: si falta un escenario pedido, el código de salida no es 0."""
    from datetime import UTC, datetime  # noqa: PLC0415

    from betsson_validator.domain.checks import SCENARIO_CHECKS, Scenario  # noqa: PLC0415
    from betsson_validator.domain.run import ScenarioRun  # noqa: PLC0415
    from betsson_validator.domain.verdict import Outcome, Testimony, WitnessKind, evaluate  # noqa: PLC0415

    now = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
    screen = Testimony(witness="p", kind=WitnessKind.VISUAL, outcome=Outcome.CONFIRMS, detail="d")
    only_one = ScenarioRun(
        scenario=Scenario.COMPLETED_SPIN,
        market="es",
        provider="Pragmatic Play",
        game="g",
        started_at=now,
        finished_at=now,
        results=tuple(
            evaluate(c.value, (screen,)) for c in SCENARIO_CHECKS[Scenario.COMPLETED_SPIN]
        ),
    )
    monkeypatch.setattr(cli, "_run_all", lambda *_args, **_kwargs: [only_one])
    monkeypatch.setattr(cli, "RapidOcrReader", lambda: None)
    assert main(["run", "--out", str(tmp_path)]) == 1
    assert only_one.status.value == "PASS"
