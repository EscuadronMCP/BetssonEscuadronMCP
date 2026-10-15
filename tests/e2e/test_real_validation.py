"""De extremo a extremo contra betsson.es real: el flujo completo desde abrir el navegador.

Juega con dinero real (una tirada mínima) y necesita IP española y las credenciales en `.env`,
así que solo se ejecuta si se pide expresamente:

    BETSSON_E2E=1 uv run pytest -m e2e

CI lo excluye (`-m "not e2e"`); en GitHub Actions el flujo real lo cubre el workflow de validación.
"""

import json
import os
from pathlib import Path

import pytest

from betsson_validator.__main__ import main

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.getenv("BETSSON_E2E") != "1",
        reason="Juega con dinero real: activar con BETSSON_E2E=1 (IP española y .env).",
    ),
]


def test_both_scenarios_pass_end_to_end_with_the_deliberate_failure_detected(
    tmp_path: Path,
) -> None:
    assert main(["run", "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert {run["scenario"] for run in report["runs"]} == {
        "completed_spin",
        "insufficient_balance",
    }
    demo = next(run["demo"] for run in report["runs"] if run["scenario"] == "completed_spin")
    assert demo is not None
    assert any(result["status"] == "FAIL" for result in demo["results"])
    assert (tmp_path / "index.html").is_file()
