"""Conversión de importes tal y como los muestra la web o el juego a Money."""

import re
from decimal import Decimal, InvalidOperation

from betsson_validator.domain.money import Money

_SYMBOLS = {"€": "EUR", "EUR": "EUR", "S/": "PEN", "PEN": "PEN", "$": "USD", "USD": "USD"}
_NUMBER = re.compile(r"[-+]?\d[\d.,\s]*")  # \s incluye espacios no separables


class AmountParseError(ValueError):
    pass


def parse_amount(text: str, decimal_separator: str = ",") -> Decimal:
    """Convierte '1.234,56' (o '1,234.56' con separador '.') en Decimal."""
    match = _NUMBER.search(text)
    if not match:
        raise AmountParseError(f"No hay ningún importe en {text!r}")
    raw = re.sub(r"\s", "", match.group(0)).rstrip(".,")
    thousands = "." if decimal_separator == "," else ","
    normalized = raw.replace(thousands, "").replace(decimal_separator, ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise AmountParseError(f"Importe no válido en {text!r}") from error


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
