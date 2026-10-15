"""Perfil aprendido de un juego: etiquetas del HUD y aspecto de sus controles.

Vive en profiles/<proveedor>/<juego>/ (profile.yaml + una imagen por control). Se genera con
`python -m betsson_validator learn` y se versiona: cualquiera puede revisar qué aprendió la IA.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import yaml

Image = npt.NDArray[np.uint8]

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"
CONTROLS = ("continue", "spin", "bet_down", "bet_up")


@dataclass
class GameProfile:
    provider: str
    game: str
    credit_label: str
    bet_label: str
    win_label: str
    templates: dict[str, Image] = field(default_factory=dict)
    # Zona de los rodillos relativa a la captura (x1, y1, x2, y2 en 0-1); None = pantalla entera.
    reels_area: tuple[float, float, float, float] | None = None
    # Dónde se lee cada valor del HUD (centro de la etiqueta, relativo 0-1): desempata etiquetas
    # repetidas, p. ej. "APUESTA" del HUD frente a la del panel de apuesta extra.
    hud_positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    learned_with: str = ""
    learned_at: str = ""

    def template(self, control: str) -> Image | None:
        return self.templates.get(control)

    def save(self, profiles_dir: Path = DEFAULT_PROFILES_DIR) -> Path:
        directory = profiles_dir / self.provider / self.game
        directory.mkdir(parents=True, exist_ok=True)
        files = {}
        for control, image in self.templates.items():
            name = f"{control}.png"
            cv2.imwrite(str(directory / name), image)
            files[control] = name
        data = {
            "provider": self.provider,
            "game": self.game,
            "labels": {"credit": self.credit_label, "bet": self.bet_label, "win": self.win_label},
            "controls": files,
            "reels_area": list(self.reels_area) if self.reels_area else None,
            "hud_positions": {k: list(v) for k, v in self.hud_positions.items()},
            "learned_with": self.learned_with,
            "learned_at": self.learned_at or datetime.now(UTC).isoformat(timespec="seconds"),
        }
        path = directory / "profile.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), "utf-8")
        return path


def load_profile(
    provider: str, game: str, profiles_dir: Path = DEFAULT_PROFILES_DIR
) -> GameProfile | None:
    directory = profiles_dir / provider / game
    path = directory / "profile.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text("utf-8"))
    templates: dict[str, Image] = {}
    for control, name in (data.get("controls") or {}).items():
        image = cv2.imread(str(directory / name))
        if image is not None:
            templates[control] = np.asarray(image, dtype=np.uint8)
    labels = data["labels"]
    return GameProfile(
        provider=data["provider"],
        game=data["game"],
        credit_label=labels["credit"],
        bet_label=labels["bet"],
        win_label=labels.get("win") or "",
        reels_area=tuple(data["reels_area"]) if data.get("reels_area") else None,
        hud_positions={
            k: (float(v[0]), float(v[1])) for k, v in (data.get("hud_positions") or {}).items()
        },
        templates=templates,
        learned_with=data.get("learned_with", ""),
        learned_at=data.get("learned_at", ""),
    )
