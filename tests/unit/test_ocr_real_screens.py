"""OCR sobre capturas reales de Sweet Bonanza 2500 en betsson.es (15/10)."""

from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import pytest

from betsson_validator.perception.hud import HudLabels, read_hud
from betsson_validator.perception.ocr import RapidOcrReader

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pragmaticplay"
LABELS = HudLabels(credit="CRÉDITO", bet="APUESTA", win="GANANCIA")


@pytest.fixture(scope="module")
def reader() -> RapidOcrReader:
    return RapidOcrReader()


def load(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None
    return np.asarray(image, dtype=np.uint8)


def test_ready_screen(reader: RapidOcrReader) -> None:
    hud = read_hud(reader.read(load("sweet_bonanza_ready.png")), LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("64.70")
    assert hud.bet is not None and hud.bet.money.amount == Decimal("2.00")
    assert hud.win is None


def test_after_spin_screen_reconciles(reader: RapidOcrReader) -> None:
    hud = read_hud(reader.read(load("sweet_bonanza_after_spin.png")), LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("64.65")
    assert hud.bet is not None and hud.bet.money.amount == Decimal("0.20")
    assert hud.win is not None and hud.win.money.amount == Decimal("0.15")
    assert hud.credit.money.currency == "EUR"
