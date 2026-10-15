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
