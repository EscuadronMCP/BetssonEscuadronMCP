"""Configuración por proveedor. Añadir un proveedor es añadir un YAML en config/providers/."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_PROVIDERS_DIR = Path(__file__).resolve().parents[3] / "config" / "providers"

Point = tuple[float, float]


class ScreenLabels(BaseModel):
    model_config = ConfigDict(frozen=True)

    credit: str
    bet: str
    win: str


class ScreenControls(BaseModel):
    """Posición de los controles relativa al iframe del juego (0-1)."""

    model_config = ConfigDict(frozen=True)

    continue_: Point = Field(alias="continue")
    spin: Point
    bet_down: Point

    @field_validator("continue_", "spin", "bet_down")
    @classmethod
    def _inside_frame(cls, point: Point) -> Point:
        if not all(0.0 <= value <= 1.0 for value in point):
            raise ValueError(f"Coordenada relativa fuera de [0, 1]: {point}")
        return point


class ScreenProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    labels: ScreenLabels
    insufficient_funds_pattern: str
    message_dismiss_label: str
    reels_region: tuple[float, float, float, float]
    controls: ScreenControls
    bet_down_presses: int = Field(ge=0, le=50)
    ready_timeout_s: int = 150
    spin_timeout_s: int = 45
    network_spin_action: str = "doSpin"

    @property
    def insufficient_funds_regex(self) -> re.Pattern[str]:
        return re.compile(self.insufficient_funds_pattern)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    filter_label: str = Field(description="Texto del chip del proveedor en el panel Filtros")
    game_slug: str = Field(
        description="Juego preferido: final de la URL /casino/<categoría>/<slug>"
    )
    game_load_timeout_s: int = 120
    screen: ScreenProfile


def load_provider(provider_id: str, providers_dir: Path = DEFAULT_PROVIDERS_DIR) -> ProviderConfig:
    path = providers_dir / f"{provider_id}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in providers_dir.glob("*.yaml"))
        raise ValueError(f"Proveedor desconocido '{provider_id}'. Disponibles: {available}")
    with path.open(encoding="utf-8") as file:
        return ProviderConfig.model_validate(yaml.safe_load(file))
