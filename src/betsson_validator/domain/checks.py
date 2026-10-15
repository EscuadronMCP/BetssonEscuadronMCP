"""Comprobaciones oficiales de cada escenario, tal y como las enumera el enunciado del reto."""

from enum import StrEnum


class Check(StrEnum):
    # Escenario 1: tirada completada
    SPIN_COMPLETED = "spin_completed"
    WAGER_MATCHES = "wager_matches"
    CURRENCY_MATCHES = "currency_matches"
    GAME_BALANCE_CONSISTENT = "game_balance_consistent"
    BETSSON_BALANCE_RECONCILES = "betsson_balance_reconciles"
    # Escenario 2: saldo insuficiente
    SPIN_REJECTED = "spin_rejected"
    INSUFFICIENT_MESSAGE_SHOWN = "insufficient_message_shown"
    BETSSON_BALANCE_UNCHANGED = "betsson_balance_unchanged"
    GAME_BALANCE_UNCHANGED = "game_balance_unchanged"


class Scenario(StrEnum):
    COMPLETED_SPIN = "completed_spin"
    INSUFFICIENT_BALANCE = "insufficient_balance"


DESCRIPTIONS: dict[Check, str] = {
    Check.SPIN_COMPLETED: "La tirada empezó y terminó (pulsar el botón no basta).",
    Check.WAGER_MATCHES: "La apuesta mostrada es la apuesta usada en la tirada.",
    Check.CURRENCY_MATCHES: "La divisa mostrada coincide con la del mercado.",
    Check.GAME_BALANCE_CONSISTENT: "El saldo del juego es coherente con la tirada completada.",
    Check.BETSSON_BALANCE_RECONCILES: (
        "El saldo de Betsson cuadra: después = antes - apuesta + premio."
    ),
    Check.SPIN_REJECTED: "La tirada se rechaza en lugar de completarse como tirada pagada.",
    Check.INSUFFICIENT_MESSAGE_SHOWN: (
        "El jugador ve un mensaje de saldo insuficiente en el idioma esperado."
    ),
    Check.BETSSON_BALANCE_UNCHANGED: "El saldo de Betsson no cambia.",
    Check.GAME_BALANCE_UNCHANGED: "El saldo del juego no cambia.",
}

SCENARIO_CHECKS: dict[Scenario, tuple[Check, ...]] = {
    Scenario.COMPLETED_SPIN: (
        Check.SPIN_COMPLETED,
        Check.WAGER_MATCHES,
        Check.CURRENCY_MATCHES,
        Check.GAME_BALANCE_CONSISTENT,
        Check.BETSSON_BALANCE_RECONCILES,
    ),
    Scenario.INSUFFICIENT_BALANCE: (
        Check.SPIN_REJECTED,
        Check.INSUFFICIENT_MESSAGE_SHOWN,
        Check.CURRENCY_MATCHES,
        Check.BETSSON_BALANCE_UNCHANGED,
        Check.GAME_BALANCE_UNCHANGED,
    ),
}

SCENARIO_TITLES: dict[Scenario, str] = {
    Scenario.COMPLETED_SPIN: "Escenario 1: tirada completada en Real Play",
    Scenario.INSUFFICIENT_BALANCE: "Escenario 2: saldo insuficiente",
}
