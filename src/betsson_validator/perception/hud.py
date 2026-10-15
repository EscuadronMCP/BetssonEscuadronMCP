"""Lectura del HUD del juego (crédito, apuesta, ganancia y mensajes) a partir del OCR.

Se busca la etiqueta que ve el jugador ("CRÉDITO", "APUESTA"…) y el importe que la acompaña,
ya sea en la misma caja de texto o en la caja más cercana a su derecha en la misma línea.
Así no hace falta calibrar regiones fijas por juego: basta con las etiquetas del proveedor.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import AmountParseError, detect_currency, parse_amount
from betsson_validator.perception.ocr import TextBox

_AMOUNT = re.compile(r"\d[\d.\s]*,\d{2}")
_PARAGRAPH_LINE_GAP = 2.2  # distancia máxima entre líneas de un mismo párrafo, en alturas


@dataclass(frozen=True)
class HudLabels:
    credit: str
    bet: str
    win: str


@dataclass(frozen=True)
class AmountReading:
    money: Money
    source_text: str
    score: float


@dataclass(frozen=True)
class HudReading:
    credit: AmountReading | None
    bet: AmountReading | None
    win: AmountReading | None
    texts: tuple[str, ...]


def _normalize(text: str) -> str:
    without_accents = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return without_accents.upper().strip()


def _starts_with_label(text: str, label: str) -> bool:
    return _normalize(text).startswith(_normalize(label))


def _amount_in(text: str, default_currency: str) -> Money | None:
    match = _AMOUNT.search(text)
    if not match:
        return None
    try:
        amount = parse_amount(match.group(0))
    except AmountParseError:
        return None
    return Money(amount=amount, currency=detect_currency(text) or default_currency)


def _same_line(a: TextBox, b: TextBox) -> bool:
    return abs(a.center_y - b.center_y) <= max(a.height, b.height) * 0.6


def find_amount(
    boxes: Sequence[TextBox], label: str, default_currency: str
) -> AmountReading | None:
    if not label.strip():
        return None  # una etiqueta vacía coincidiría con cualquier texto
    for box in boxes:
        if not _starts_with_label(box.text, label):
            continue
        rest = box.text[len(label) :] if len(box.text) > len(label) else ""
        money = _amount_in(rest, default_currency)
        if money is not None:
            return AmountReading(money=money, source_text=box.text, score=box.score)
        neighbours = sorted(
            (b for b in boxes if b is not box and _same_line(b, box) and b.x > box.x),
            key=lambda b: b.x,
        )
        for neighbour in neighbours:
            money = _amount_in(neighbour.text, default_currency)
            if money is not None:
                text = f"{box.text} {neighbour.text}"
                return AmountReading(
                    money=money, source_text=text, score=min(box.score, neighbour.score)
                )
    return None


def read_hud(boxes: Sequence[TextBox], labels: HudLabels, default_currency: str) -> HudReading:
    return HudReading(
        credit=find_amount(boxes, labels.credit, default_currency),
        bet=find_amount(boxes, labels.bet, default_currency),
        win=find_amount(boxes, labels.win, default_currency),
        texts=tuple(box.text for box in boxes),
    )


def find_message(boxes: Sequence[TextBox], pattern: re.Pattern[str]) -> str | None:
    """Busca un mensaje (p. ej. saldo insuficiente) y devuelve el párrafo completo que lo contiene.

    El OCR parte un párrafo en líneas: tras encontrar la línea que coincide se añaden las que
    siguen justo debajo y alineadas con ella, para que el informe muestre el mensaje entero.
    """
    for box in boxes:
        if pattern.search(box.text):
            return _paragraph(boxes, box)
    joined = " ".join(box.text for box in sorted(boxes, key=lambda b: (b.y, b.x)))
    match = pattern.search(joined)
    return match.group(0) if match else None


def _paragraph(boxes: Sequence[TextBox], first: TextBox) -> str:
    lines = [first]
    current = first
    for box in sorted(boxes, key=lambda b: b.y):
        below = 0 < box.y - current.y <= current.height * _PARAGRAPH_LINE_GAP
        aligned = abs(box.center_x - first.center_x) <= first.width / 2
        if below and aligned:
            lines.append(box)
            current = box
    return " ".join(line.text.strip() for line in lines)
