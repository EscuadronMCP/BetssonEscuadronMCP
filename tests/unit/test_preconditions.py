"""Nunca se gira con dinero real si el estado no es el que el escenario necesita."""

from decimal import Decimal

import pytest

from betsson_validator.domain.money import Money
from betsson_validator.scenarios.preconditions import (
    PreconditionError,
    check_bet,
    require_funds,
    require_no_funds,
)


def eur(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="EUR")


MAX = Decimal("0.50")


def test_minimum_bet_within_limits_is_accepted() -> None:
    assert check_bet(eur("0.20"), MAX, "EUR") == eur("0.20")


@pytest.mark.parametrize(
    "bet",
    [None, eur("0.00"), eur("-0.20"), eur("0.60"), Money(amount=Decimal("0.20"), currency="USD")],
)
def test_unreadable_zero_negative_excessive_or_foreign_bet_stops(bet: Money | None) -> None:
    with pytest.raises(PreconditionError):
        check_bet(bet, MAX, "EUR")


def test_funded_scenario_needs_funds_in_betsson_and_in_the_game() -> None:
    require_funds(eur("10.00"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("0.10"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("10.00"), eur("0.10"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("10.00"), None, eur("0.20"))


def test_no_balance_account_with_money_never_spins() -> None:
    """Auditoría: con 10 € en la cuenta "sin saldo" el escenario 2 llegaba a girar."""
    with pytest.raises(PreconditionError, match="tiene fondos"):
        require_no_funds(eur("10.00"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_no_funds(eur("0.00"), eur("0.20"), eur("0.20"))
    require_no_funds(eur("0.00"), eur("0.00"), eur("0.20"))
    require_no_funds(eur("0.10"), None, eur("0.20"))
