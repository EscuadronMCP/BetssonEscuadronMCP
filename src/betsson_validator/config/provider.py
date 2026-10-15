"""Configuración por proveedor. Añadir un proveedor es añadir un YAML en config/providers/.

Solo contiene lo que es del proveedor en el casino. Lo que depende de cada juego (etiquetas del
HUD, aspecto de los controles) se aprende y vive en profiles/ (ver profiles.py).
"""

from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PROVIDERS_DIR = Path(__file__).resolve().parents[3] / "config" / "providers"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    filter_label: str = Field(description="Texto del chip del proveedor en el panel Filtros")
    game_slug: str = Field(
        description="Juego por defecto: final de la URL /casino/<categoría>/<slug>"
    )
    game_load_timeout_s: int = 120
    max_bet: Decimal = Field(
        default=Decimal("0.50"), description="Salvaguarda: no se gira si la apuesta es mayor"
    )
    network_witness: Literal["pragmatic"] | None = Field(
        default=None, description="Testigo de red disponible para este proveedor, si lo hay"
    )


def load_provider(provider_id: str, providers_dir: Path = DEFAULT_PROVIDERS_DIR) -> ProviderConfig:
    path = providers_dir / f"{provider_id}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in providers_dir.glob("*.yaml"))
        raise ValueError(f"Proveedor desconocido '{provider_id}'. Disponibles: {available}")
    with path.open(encoding="utf-8") as file:
        return ProviderConfig.model_validate(yaml.safe_load(file))
