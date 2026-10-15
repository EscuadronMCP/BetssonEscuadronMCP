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
    assert check_bet(eur("0.20"), MAX, "EUR", ("EUR",)) == eur("0.20")


@pytest.mark.parametrize(
    "bet",
    [None, eur("0.00"), eur("-0.20"), eur("0.60"), Money(amount=Decimal("0.20"), currency="USD")],
)
def test_unreadable_zero_negative_excessive_or_foreign_bet_stops(bet: Money | None) -> None:
    with pytest.raises(PreconditionError):
        check_bet(bet, MAX, "EUR", ("EUR",) if bet is None or bet.currency == "EUR" else ("USD",))


@pytest.mark.parametrize("observed", [(), ("USD",), ("EUR", "USD")])
def test_currency_must_be_seen_on_screen_not_taken_from_config(observed: tuple[str, ...]) -> None:
    """Sin símbolo leído, la divisa de `bet` viene de la configuración."""
    with pytest.raises(PreconditionError, match="Divisa vista"):
        check_bet(eur("0.20"), MAX, "EUR", observed)


def test_funded_scenario_needs_funds_in_betsson_and_in_the_game() -> None:
    require_funds(eur("10.00"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("0.10"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("10.00"), eur("0.10"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_funds(eur("10.00"), None, eur("0.20"))


def test_no_balance_account_with_money_never_spins() -> None:
    """Con 10 € en la cuenta "sin saldo" el escenario 2 llegaba a girar."""
    with pytest.raises(PreconditionError, match="tiene fondos"):
        require_no_funds(eur("10.00"), eur("10.00"), eur("0.20"))
    with pytest.raises(PreconditionError):
        require_no_funds(eur("0.00"), eur("0.20"), eur("0.20"))
    require_no_funds(eur("0.00"), eur("0.00"), eur("0.20"))


def test_unknown_game_credit_cannot_confirm_insufficient_funds() -> None:
    """Crédito desconocido no autoriza el intento."""
    with pytest.raises(PreconditionError, match="crédito del juego"):
        require_no_funds(eur("0.10"), None, eur("0.20"))


def test_a_bet_above_the_known_minimum_never_spins() -> None:
    """Que falte el botón de bajar no prueba que sea la mínima."""
    from betsson_validator.scenarios.preconditions import require_known_minimum  # noqa: PLC0415

    require_known_minimum(eur("0.20"), Decimal("0.20"))
    require_known_minimum(eur("0.40"), None)  # sin mínimo conocido manda el tope max_bet
    with pytest.raises(PreconditionError, match="mínima conocida"):
        require_known_minimum(eur("0.40"), Decimal("0.20"))
