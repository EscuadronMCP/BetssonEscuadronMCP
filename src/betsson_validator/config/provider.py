"""Configuración por proveedor. Añadir un proveedor es añadir un YAML en config/providers/."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PROVIDERS_DIR = Path(__file__).resolve().parents[3] / "config" / "providers"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    filter_label: str = Field(description="Texto del chip del proveedor en el panel Filtros")
    game_slug: str = Field(
        description="Juego preferido: final de la URL /casino/<categoría>/<slug>"
    )
    game_load_timeout_s: int = 120


def load_provider(provider_id: str, providers_dir: Path = DEFAULT_PROVIDERS_DIR) -> ProviderConfig:
    path = providers_dir / f"{provider_id}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in providers_dir.glob("*.yaml"))
        raise ValueError(f"Proveedor desconocido '{provider_id}'. Disponibles: {available}")
    with path.open(encoding="utf-8") as file:
        return ProviderConfig.model_validate(yaml.safe_load(file))
