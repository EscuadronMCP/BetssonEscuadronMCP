"""Lectura del HUD del juego (crédito, apuesta, ganancia y mensajes) a partir del OCR.

Se busca la etiqueta que ve el jugador ("CRÉDITO", "APUESTA"…) y el importe que la acompaña,
ya sea en la misma caja de texto o en la caja más cercana a su derecha en la misma línea.
Así no hace falta calibrar regiones fijas por juego: basta con las etiquetas del proveedor.

Para no atribuir a una etiqueta el importe de otra: la etiqueta debe ser una palabra completa,
la búsqueda a la derecha se detiene en la siguiente etiqueta del HUD o si el hueco es grande,
y se descartan lecturas con poca confianza del OCR.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import AmountParseError, detect_currency, parse_amount
from betsson_validator.perception.ocr import TextBox

# Importe con dos decimales, signo opcional y cualquier separador ("193,74", "193.74",
# "1.234,56", "1,234.56", "1 234,56"). Los miles van en grupos de tres: "10 0,15" son dos
# textos ("10" y "0,15"), no "100,15".
_AMOUNT = re.compile(r"(?<![\d.,])-?\s?(?:\d{1,3}(?:[.,\s]\d{3})+|\d+)[.,]\d{2}(?!\d)")
_MINUS_SIGNS = str.maketrans({"\u2212": "-", "\u2013": "-"})
# El OCR confunde a veces un 0 aislado con O o D ("APUESTA D,10 €", visto en Big Bass).
_OCR_ZERO = re.compile(r"(?<![A-Za-z\d])[ODo](?=[.,]\d{2}(?!\d))")
_PARAGRAPH_LINE_GAP = 2.2  # distancia máxima entre líneas de un mismo párrafo, en alturas
_MAX_LABEL_GAP = 8.0  # hueco máximo entre etiqueta e importe, en alturas de texto
MIN_OCR_SCORE = 0.5  # por debajo, el OCR no está seguro de lo que lee: no sirve como testigo


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
    x: float = 0.0  # centro de la etiqueta en la captura (px): permite elegir entre duplicadas
    y: float = 0.0


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
    """El texto empieza por la etiqueta como palabra completa ("APUESTAS" no es "APUESTA")."""
    normalized, wanted = _normalize(text), _normalize(label)
    if not normalized.startswith(wanted):
        return False
    rest = normalized[len(wanted) :]
    # Una letra pegada cambia la palabra ("APUESTAS"); un dígito pegado es el importe que el
    # OCR juntó sin espacio ("CRÉDITO192,25€", visto en Big Bass).
    return not rest or not rest[0].isalpha() or not wanted[-1].isalnum()


def _clean(text: str) -> str:
    """Signos menos tipográficos como "-" y un 0 leído como O o D."""
    return _OCR_ZERO.sub("0", text.translate(_MINUS_SIGNS))


def _amount_in(text: str, default_currency: str) -> Money | None:
    match = _AMOUNT.search(_clean(text))
    if not match:
        return None
    try:
        amount = parse_amount(match.group(0))
    except AmountParseError:
        return None
    return Money(amount=amount, currency=detect_currency(text) or default_currency)


def _own_amount(rest: str, stop_labels: Sequence[str], default_currency: str) -> Money | None:
    """Importe que sigue a la etiqueta dentro de la misma caja, salvo que antes aparezca otra
    etiqueta del HUD ("CRÉDITO APUESTA 0,20 €": ese importe es de la apuesta)."""
    cleaned = _clean(rest)
    match = _AMOUNT.search(cleaned)
    if match is None:
        return None
    before = _normalize(cleaned[: match.start()])
    if any(_normalize(other) in before for other in stop_labels if other.strip()):
        return None
    return _amount_in(rest, default_currency)


def _same_line(a: TextBox, b: TextBox) -> bool:
    return abs(a.center_y - b.center_y) <= max(a.height, b.height) * 0.6


def _value_to_the_right(
    boxes: Sequence[TextBox], box: TextBox, stop_labels: Sequence[str], default_currency: str
) -> tuple[Money, TextBox] | None:
    """Primer importe a la derecha de la etiqueta, sin cruzar otra etiqueta ni un hueco grande."""
    neighbours = sorted(
        (b for b in boxes if b is not box and _same_line(b, box) and b.x > box.x),
        key=lambda b: b.x,
    )
    right_edge = box.x + box.width
    for neighbour in neighbours:
        if neighbour.x - right_edge > _MAX_LABEL_GAP * box.height:
            return None
        if any(_starts_with_label(neighbour.text, other) for other in stop_labels if other.strip()):
            return None
        money = _amount_in(neighbour.text, default_currency)
        if money is not None:
            return money, neighbour
        right_edge = neighbour.x + neighbour.width
    return None


def find_amounts(
    boxes: Sequence[TextBox],
    label: str,
    default_currency: str,
    stop_labels: Sequence[str] = (),
) -> list[AmountReading]:
    """Todas las lecturas "etiqueta + importe" de la pantalla (puede haber etiquetas repetidas).

    `stop_labels` son las demás etiquetas del HUD: su importe nunca se atribuye a esta.
    """
    if not label.strip():
        return []  # una etiqueta vacía coincidiría con cualquier texto
    readings: list[AmountReading] = []
    for box in boxes:
        if box.score < MIN_OCR_SCORE or not _starts_with_label(box.text, label):
            continue
        money = _own_amount(box.text[len(label) :], stop_labels, default_currency)
        if money is not None:
            readings.append(AmountReading(money, box.text, box.score, box.center_x, box.center_y))
            continue
        found = _value_to_the_right(boxes, box, stop_labels, default_currency)
        if found is not None and found[1].score >= MIN_OCR_SCORE:
            money, value = found
            score = min(box.score, value.score)
            text = f"{box.text} {value.text}"
            readings.append(AmountReading(money, text, score, box.center_x, box.center_y))
    return readings


def find_amount(
    boxes: Sequence[TextBox],
    label: str,
    default_currency: str,
    near: tuple[float, float] | None = None,
    stop_labels: Sequence[str] = (),
) -> AmountReading | None:
    """La lectura de esa etiqueta; si se repite, la más cercana a `near` (posición aprendida)."""
    readings = find_amounts(boxes, label, default_currency, stop_labels)
    if not readings:
        return None
    if near is None:
        return readings[0]
    return min(readings, key=lambda r: (r.x - near[0]) ** 2 + (r.y - near[1]) ** 2)


def read_hud(
    boxes: Sequence[TextBox],
    labels: HudLabels,
    default_currency: str,
    anchors: dict[str, tuple[float, float]] | None = None,
) -> HudReading:
    """Lee el HUD; `anchors` (px) desempata etiquetas repetidas con la posición aprendida."""
    near = anchors or {}
    every = (labels.credit, labels.bet, labels.win)

    def read(name: str, label: str) -> AmountReading | None:
        others = tuple(other for other in every if other != label)
        return find_amount(boxes, label, default_currency, near.get(name), others)

    return HudReading(
        credit=read("credit", labels.credit),
        bet=read("bet", labels.bet),
        win=read("win", labels.win),
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
