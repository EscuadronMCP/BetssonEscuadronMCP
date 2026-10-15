"""Lo observado en cada escenario, leído de sus evidencias para mostrarlo en el informe.

El ejecutor guarda en la carpeta del escenario `resumen_observado.json` (valores de cada testigo,
serie de movimiento y umbrales) y `eventos_del_juego.json`. El informe los lee de ahí: así muestra
exactamente lo que quedó como evidencia, sin depender de objetos en memoria.
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SUMMARY_FILE = "resumen_observado.json"
EVENTS_FILE = "eventos_del_juego.json"


@dataclass(frozen=True)
class Observed:
    data: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    def get(self, *keys: str) -> Any:  # noqa: ANN401 - valor JSON arbitrario
        """Valor anidado o None (p. ej. get("network", "balance_after"))."""
        value: Any = self.data
        for key in keys:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value


def load_observed(folder: Path) -> Observed | None:
    """None si el escenario no llegó a observar nada (p. ej. falló antes de girar)."""
    data = _read_json(folder / SUMMARY_FILE)
    if not isinstance(data, dict):
        return None
    events = _read_json(folder / EVENTS_FILE)
    records = [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
    return Observed(data, records)


def _read_json(path: Path) -> Any:  # noqa: ANN401 - JSON arbitrario
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def amount(value: Any) -> Decimal | None:  # noqa: ANN401 - texto o número del JSON
    """Importe de "193.21 EUR", "193.21" o 193.21; None si no es un número finito."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).split()[0] if str(value).strip() else ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def currency(value: Any) -> str | None:  # noqa: ANN401 - texto del JSON
    parts = str(value).split() if value is not None else []
    return parts[1] if len(parts) > 1 else None
