"""Condiciones que deben cumplirse ANTES de pulsar girar (se juega con dinero real).

Si no se cumplen, no se gira: la ejecución termina en FAIL con el motivo. Así una cuenta
equivocada (p. ej. la "sin saldo" con dinero) nunca gasta una tirada ni produce un PASS falso.
"""

from decimal import Decimal

from betsson_validator.domain.money import Money


class PreconditionError(RuntimeError):
    """No es seguro o no tiene sentido girar en este estado."""


def check_bet(
    bet: Money | None, max_bet: Decimal, currency: str, observed_currencies: tuple[str, ...]
) -> Money:
    """La apuesta visible: leída, positiva, en la divisa del mercado y sin superar el tope.

    La divisa debe VERSE en el marcador (`observed_currencies`): la que trae `bet` puede venir
    de la configuración del mercado cuando el OCR no lee el símbolo.
    """
    if bet is None:
        raise PreconditionError("No se pudo leer la apuesta en pantalla. No se gira.")
    if set(observed_currencies) != {currency}:
        seen = ", ".join(observed_currencies) or "ninguna"
        raise PreconditionError(
            f"Divisa vista en el marcador del juego: {seen}; esperada {currency}. No se gira."
        )
    if bet.amount <= 0:
        raise PreconditionError(f"Apuesta mostrada {bet}: no es positiva. No se gira.")
    if bet.amount > max_bet:
        raise PreconditionError(
            f"Apuesta mostrada {bet}: supera el máximo de seguridad {max_bet}. No se gira."
        )
    return bet


def require_funds(betsson: Money, credit: Money | None, bet: Money) -> None:
    """Escenario 1: la cuenta debe poder pagar la apuesta en Betsson y en el juego."""
    if credit is None:
        raise PreconditionError("No se pudo leer el crédito del juego. No se gira.")
    for name, balance in (("Betsson", betsson), ("el juego", credit)):
        if balance.amount < bet.amount:
            raise PreconditionError(
                f"Saldo en {name} {balance} menor que la apuesta {bet}: la cuenta con saldo no "
                "tiene fondos. No se gira."
            )


def require_no_funds(betsson: Money, credit: Money | None, bet: Money) -> None:
    """Escenario 2: la cuenta NO debe poder pagar la apuesta (si no, giraría con dinero real)."""
    if credit is None:
        raise PreconditionError(
            "No se pudo leer el crédito del juego: no se puede confirmar que la cuenta no tenga "
            "saldo. No se gira."
        )
    for name, balance in (("Betsson", betsson), ("el juego", credit)):
        if balance is not None and balance.amount >= bet.amount:
            raise PreconditionError(
                f"Saldo en {name} {balance} suficiente para la apuesta {bet}: la cuenta "
                '"sin saldo" tiene fondos. No se gira.'
            )
