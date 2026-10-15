from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Money(BaseModel):
    """Importe con divisa. Se usa Decimal para no arrastrar errores de coma flotante."""

    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)

    def _require_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(f"Divisas distintas: {self.currency} y {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


def expected_amount_after(before: Decimal, wager: Decimal, payout: Decimal) -> Decimal:
    """Regla del reto: saldo después = saldo antes - apuesta + premio (misma divisa)."""
    return before - wager + payout


def expected_balance_after(before: Money, wager: Money, payout: Money) -> Money:
    """La regla del reto con divisas comprobadas."""
    return before - wager + payout


def balances_reconcile(before: Money, after: Money, wager: Money, payout: Money) -> bool:
    """Indica si el saldo observado tras el giro cuadra con la apuesta y el premio."""
    expected = expected_balance_after(before, wager, payout)
    return expected.currency == after.currency and expected.amount == after.amount
