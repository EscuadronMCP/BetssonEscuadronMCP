"""Conversión de importes tal y como los muestra la web o el juego a Money."""

import re
from decimal import Decimal, InvalidOperation

from betsson_validator.domain.money import Money

_SYMBOLS = {"€": "EUR", "EUR": "EUR", "S/": "PEN", "PEN": "PEN", "$": "USD", "USD": "USD"}
_NUMBER = re.compile(r"[-+]?\d[\d.,\s]*")  # \s incluye espacios no separables
_DECIMALS = 2


class AmountParseError(ValueError):
    pass


def parse_amount(text: str, decimal_separator: str | None = None) -> Decimal:
    """Convierte un importe escrito como lo muestra un proveedor en Decimal.

    Cada proveedor escribe los importes a su manera ("193,74 €", "€193.74", "1.234,56",
    "1,234.56"). Sin `decimal_separator`, se deduce: es decimal el último separador seguido
    de exactamente dos cifras; el resto son separadores de miles.
    """
    match = _NUMBER.search(text)
    if not match:
        raise AmountParseError(f"No hay ningún importe en {text!r}")
    raw = re.sub(r"\s", "", match.group(0)).rstrip(".,")
    separator = decimal_separator or _guess_decimal_separator(raw)
    integer, _, decimals = raw.rpartition(separator) if separator else (raw, "", "")
    if not separator or not integer:
        integer, decimals = raw, ""
    digits = re.sub(r"[.,]", "", integer)
    normalized = f"{digits}.{decimals}" if decimals else digits
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise AmountParseError(f"Importe no válido en {text!r}") from error


def _guess_decimal_separator(raw: str) -> str | None:
    last = max(raw.rfind(","), raw.rfind("."))
    if last == -1:
        return None
    decimals = raw[last + 1 :]
    return raw[last] if len(decimals) == _DECIMALS and decimals.isdigit() else None


def detect_currency(text: str) -> str | None:
    """Devuelve el código ISO de la divisa que aparece en el texto, si aparece alguna."""
    for symbol, code in _SYMBOLS.items():
        if symbol in text:
            return code
    return None


def parse_money(text: str, decimal_separator: str = ",") -> Money:
    currency = detect_currency(text)
    if currency is None:
        raise AmountParseError(f"No hay divisa en {text!r}")
    return Money(amount=parse_amount(text, decimal_separator), currency=currency)
