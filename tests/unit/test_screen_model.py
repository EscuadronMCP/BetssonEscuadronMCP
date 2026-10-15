"""Readaptación ante cambios del proveedor, con capturas reales y una IA simulada (sin coste).

Se comprueba que: un botón movido se encuentra sin IA; un texto cambiado o un botón rediseñado
se reaprenden con la IA y se anota en el informe; y sin IA el fallo es honesto (no inventa).
"""

from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import pytest

from betsson_validator.game.player import GameError, ScreenModel
from betsson_validator.perception.learner import Box, ScreenAnalysis
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.perception.templates import crop
from betsson_validator.profiles import GameProfile, load_profile

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pragmaticplay"
SPIN_BOX = (651, 415, 92, 82)


def load(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None
    return np.asarray(image, dtype=np.uint8)


class FakeLearner:
    """Simula la IA devolviendo lo que se ve en la captura real; cuenta cuántas veces se usa."""

    def __init__(self, analysis: ScreenAnalysis) -> None:
        self.analysis = analysis
        self.calls = 0

    def analyze(self, image: np.ndarray, *, model: str | None = None) -> ScreenAnalysis:
        self.calls += 1
        return self.analysis


REAL_ANALYSIS = ScreenAnalysis(
    is_intro_screen=False,
    continue_button=None,
    spin_button=Box(x=651, y=415, width=92, height=82),
    bet_decrease_button=Box(x=608, y=440, width=34, height=34),
    bet_increase_button=Box(x=746, y=440, width=34, height=34),
    reels_area=Box(x=224, y=50, width=584, height=388),
    credit_label="CRÉDITO",
    bet_label="APUESTA",
    win_label="GANANCIA",
    message_text=None,
)


@pytest.fixture(scope="module")
def reader() -> RapidOcrReader:
    return RapidOcrReader()


def profile(**changes: object) -> GameProfile:
    base = GameProfile("pragmaticplay", "sweet-bonanza-2500", "CRÉDITO", "APUESTA", "GANANCIA")
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def test_moved_button_is_found_without_ai(reader: RapidOcrReader) -> None:
    ready = load("sweet_bonanza_ready.png")
    template = crop(ready, SPIN_BOX)
    moved = ready.copy()
    x, y, w, h = SPIN_BOX
    moved[y : y + h, x : x + w] = moved[y - h : y, x : x + w]
    moved[30 : 30 + h, 40 : 40 + w] = template
    learner = FakeLearner(REAL_ANALYSIS)
    model = ScreenModel(profile(templates={"spin": template}), reader, "EUR", learner)
    point = model.locate_or_learn("spin", moved)
    assert point == pytest.approx(((40 + w / 2) / 896, (30 + h / 2) / 504), abs=0.01)
    assert learner.calls == 0
    assert model.notes == []


def test_changed_labels_are_relearned(reader: RapidOcrReader) -> None:
    learner = FakeLearner(REAL_ANALYSIS)
    model = ScreenModel(profile(credit_label="SALDO", bet_label="STAKE"), reader, "EUR", learner)
    hud, _ = model.read_or_learn(load("sweet_bonanza_ready.png"))
    assert hud.credit is not None and hud.credit.money.amount == Decimal("64.70")
    assert hud.bet is not None and hud.bet.money.amount == Decimal("2.00")
    assert learner.calls == 1
    assert "reaprendido" in model.notes[0]


def test_redesigned_button_is_relearned(reader: RapidOcrReader) -> None:
    ready = load("sweet_bonanza_ready.png")
    old_design = np.full((60, 60, 3), (0, 0, 255), dtype=np.uint8)  # aspecto que ya no existe
    learner = FakeLearner(REAL_ANALYSIS)
    model = ScreenModel(profile(templates={"spin": old_design}), reader, "EUR", learner)
    point = model.locate_or_learn("spin", ready)
    assert point == pytest.approx(((651 + 46) / 896, (415 + 41) / 504), abs=0.02)
    assert learner.calls == 1


def test_without_ai_a_changed_screen_fails_honestly(reader: RapidOcrReader) -> None:
    model = ScreenModel(profile(credit_label="SALDO", bet_label="STAKE"), reader, "EUR", None)
    hud, _ = model.read_or_learn(load("sweet_bonanza_ready.png"))
    assert hud.credit is None and hud.bet is None
    with pytest.raises(GameError, match="spin"):
        model.locate_or_learn("spin", load("sweet_bonanza_ready.png"))


def test_ai_is_used_at_most_once_per_run(reader: RapidOcrReader) -> None:
    learner = FakeLearner(REAL_ANALYSIS.model_copy(update={"spin_button": None}))
    model = ScreenModel(profile(), reader, "EUR", learner)
    image = load("sweet_bonanza_ready.png")
    for _ in range(3):
        with pytest.raises(GameError):
            model.locate_or_learn("spin", image)
    assert learner.calls == 1


def test_profile_round_trip(tmp_path: Path) -> None:
    ready = load("sweet_bonanza_ready.png")
    original = profile(templates={"spin": crop(ready, SPIN_BOX)}, reels_area=(0.25, 0.1, 0.9, 0.87))
    original.learned_with = "claude-haiku-5-5"
    original.save(tmp_path)
    loaded = load_profile("pragmaticplay", "sweet-bonanza-2500", tmp_path)
    assert loaded is not None
    assert loaded.credit_label == "CRÉDITO"
    assert loaded.reels_area == (0.25, 0.1, 0.9, 0.87)
    assert loaded.template("spin") is not None
    assert load_profile("pragmaticplay", "otro-juego", tmp_path) is None
