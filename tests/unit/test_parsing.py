from decimal import Decimal

import pytest

from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import (
    AmountParseError,
    detect_currency,
    parse_amount,
    parse_money,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("64,70 €", Decimal("64.70")),
        ("1.234,56 €", Decimal("1234.56")),
        ("€ 0,20", Decimal("0.20")),
        ("CRÉDITO 64,70 €", Decimal("64.70")),
        ("2\u00a0000,00 €", Decimal("2000.00")),
        ("5 €", Decimal("5")),
    ],
)
def test_spanish_amounts(text: str, expected: Decimal) -> None:
    assert parse_amount(text) == expected


def test_dot_decimal_separator() -> None:
    assert parse_amount("1,234.56", decimal_separator=".") == Decimal("1234.56")


def test_parse_money_with_currency() -> None:
    assert parse_money("64,70 €") == Money(amount=Decimal("64.70"), currency="EUR")


def test_currency_detection() -> None:
    assert detect_currency("APUESTA 2,00 €") == "EUR"
    assert detect_currency("S/ 10.00") == "PEN"
    assert detect_currency("Saldo") is None


@pytest.mark.parametrize("text", ["Saldo", "", "€"])
def test_text_without_amount_fails(text: str) -> None:
    with pytest.raises(AmountParseError):
        parse_amount(text)


def test_money_without_currency_fails() -> None:
    with pytest.raises(AmountParseError, match="divisa"):
        parse_money("64,70")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("€193.74", Decimal("193.74")),  # Play'n GO
        ("Saldo: €193.74", Decimal("193.74")),
        ("1,234.56", Decimal("1234.56")),
        ("1.234,56 €", Decimal("1234.56")),
        ("€1,500", Decimal("1500")),  # coma de miles, sin decimales
        ("12.000", Decimal("12000")),  # punto de miles, sin decimales
    ],
)
def test_any_provider_number_format(text: str, expected: Decimal) -> None:
    assert parse_amount(text) == expected
