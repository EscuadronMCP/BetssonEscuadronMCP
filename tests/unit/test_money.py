from decimal import Decimal

import pytest

from betsson_validator.domain.money import Money, balances_reconcile, expected_balance_after


def eur(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="EUR")


def test_losing_spin_subtracts_wager() -> None:
    assert expected_balance_after(eur("10.00"), eur("0.20"), eur("0")) == eur("9.80")


def test_winning_spin_adds_payout() -> None:
    assert balances_reconcile(eur("10.00"), eur("10.30"), eur("0.20"), eur("0.50"))


def test_mismatch_is_detected() -> None:
    assert not balances_reconcile(eur("10.00"), eur("10.00"), eur("0.20"), eur("0"))


def test_decimal_avoids_float_drift() -> None:
    assert balances_reconcile(eur("0.30"), eur("0.10"), eur("0.20"), eur("0"))


def test_mixing_currencies_is_rejected() -> None:
    with pytest.raises(ValueError, match="Divisas distintas"):
        eur("1") - Money(amount=Decimal("1"), currency="PEN")
