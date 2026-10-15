"""Cajas de texto reales devueltas por RapidOCR sobre capturas de Sweet Bonanza 2500 (15/10)."""

import re
from decimal import Decimal

from betsson_validator.perception.hud import HudLabels, find_message, read_hud
from betsson_validator.perception.ocr import TextBox

LABELS = HudLabels(credit="CRÉDITO", bet="APUESTA", win="GANANCIA")


def box(text: str, x: int, y: int, score: float = 0.98) -> TextBox:
    return TextBox(text=text, score=score, x=x, y=y, width=8 * len(text), height=16)


AFTER_SPIN = [
    box("APUESTAS", 98, 190),
    box("10 0,15 €", 92, 411),
    box("GANANCIA 0,15 €", 325, 435),
    box("CRÉDITO 64,65 €", 147, 450),
    box("APUESTA 0,20 €", 145, 468),
]


def test_reads_real_hud_after_spin() -> None:
    hud = read_hud(AFTER_SPIN, LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("64.65")
    assert hud.bet is not None and hud.bet.money.amount == Decimal("0.20")
    assert hud.win is not None and hud.win.money.amount == Decimal("0.15")
    assert hud.credit.money.currency == "EUR"


def test_label_with_plural_does_not_hide_the_real_bet() -> None:
    # "APUESTAS ESPECIALES" empieza por "APUESTA" pero no lleva importe: se ignora.
    hud = read_hud(AFTER_SPIN, LABELS, "EUR")
    assert hud.bet is not None and hud.bet.source_text == "APUESTA 0,20 €"


def test_amount_in_separate_box_on_same_line() -> None:
    boxes = [box("CRÉDITO", 100, 450), box("64,70 €", 180, 452), box("2,00 €", 180, 600)]
    hud = read_hud(boxes, LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("64.70")


def test_accents_are_ignored_in_labels() -> None:
    hud = read_hud([box("CREDITO 1.234,50 €", 0, 0)], LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("1234.50")


def test_missing_values_are_none() -> None:
    hud = read_hud([box("¡HAGA SU APUESTA!", 352, 443)], LABELS, "EUR")
    assert hud.credit is None and hud.bet is None and hud.win is None


def test_currency_defaults_to_market_when_symbol_not_read() -> None:
    hud = read_hud([box("CRÉDITO 64,70", 0, 0)], LABELS, "EUR")
    assert hud.credit is not None and hud.credit.money.currency == "EUR"


def test_find_message_across_boxes() -> None:
    pattern = re.compile(r"(?i)saldo\s+insuficiente")
    boxes = [box("Saldo", 10, 10), box("insuficiente", 80, 10)]
    assert find_message(boxes, pattern) == "Saldo insuficiente"
    assert find_message([box("Hola", 0, 0)], pattern) is None


def test_duplicated_label_is_resolved_with_the_learned_position() -> None:
    # Big Bass: "APUESTA" del panel de apuesta extra (arriba a la derecha) y la del HUD (abajo).
    boxes = [box("APUESTA 0,60 €", 797, 70), box("APUESTA 0,40 €", 144, 468)]
    near_hud = {"bet": (180.0, 476.0)}
    hud = read_hud(boxes, LABELS, "EUR", near_hud)
    assert hud.bet is not None and hud.bet.money.amount == Decimal("0.40")
    without_anchor = read_hud(boxes, LABELS, "EUR")
    assert without_anchor.bet is not None and without_anchor.bet.money.amount == Decimal("0.60")


def test_playngo_hud_format() -> None:
    # Cajas reales de RapidOCR sobre Viking Runecraft 1000 (Play'n GO, 15/10).
    boxes = [box("Saldo: €193.74", 38, 490), box("Apuesta: €1.50", 111, 492)]
    labels = HudLabels(credit="Saldo:", bet="Apuesta:", win="Ganancias:")
    hud = read_hud(boxes, labels, "EUR")
    assert hud.credit is not None and hud.credit.money.amount == Decimal("193.74")
    assert hud.credit.money.currency == "EUR"
    assert hud.bet is not None and hud.bet.money.amount == Decimal("1.50")
