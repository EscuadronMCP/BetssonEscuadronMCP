"""Lo observado en una ejecución, en tipos de dominio (independiente de navegador y proveedor)."""

from dataclasses import dataclass
from decimal import Decimal

from betsson_validator.domain.money import Money


@dataclass(frozen=True)
class ScreenSnapshot:
    """Lo que el jugador ve en el HUD del juego en un momento dado."""

    credit: Money | None
    bet: Money | None
    win: Money | None
    # Divisas que muestra el HUD (crédito, apuesta, premio); más de una es una incoherencia.
    currencies_seen: tuple[str, ...]
    message: str | None
    evidence: str
    # Otro aviso visible del juego (sesión expirada, error de conexión…), si lo hubo.
    notice: str | None = None
    # False si el marcador seguía cambiando al leerlo: no vale como prueba del saldo.
    settled: bool = True


@dataclass(frozen=True)
class MotionSummary:
    started: bool
    completed: bool
    samples: int
    peak: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkSummary:
    """Lo que dijo el servidor del juego. `spin_requested` es False si no hubo petición de tirada.

    La apuesta pedida por el cliente no prueba nada por sí sola: cuenta la que el servidor
    acepta en su respuesta (`wager_accepted`) y el premio que declara (`declared_win`).
    """

    spin_requested: bool
    settled: bool = False
    wager_requested: Decimal | None = None
    wager_accepted: Decimal | None = None
    declared_win: Decimal | None = None
    balance_before: Decimal | None = None
    balance_after: Decimal | None = None
    evidence: str = ""
    # Salud de la captura: sin tráfico observado o con respuestas ilegibles durante la tirada,
    # la ausencia de una petición no prueba nada.
    observed_calls: int = 0
    unreadable: int = 0

    @property
    def reliable(self) -> bool:
        return self.observed_calls > 0 and self.unreadable == 0


@dataclass(frozen=True)
class GameEventsSummary:
    """Lo que el juego comunicó al casino por postMessage durante la tirada."""

    received: bool
    round_started: bool = False
    round_ended: bool = False
    low_balance: bool = False
    bet: Decimal | None = None
    win: Decimal | None = None
    balance_before: Decimal | None = None
    balance_after: Decimal | None = None
    languages: tuple[str, ...] = ()
    currencies: tuple[str, ...] = ()
    # Incoherencias del propio canal (rondas desordenadas o repetidas, valores contradictorios):
    # si hay alguna, el testigo contradice en lugar de confirmar.
    anomalies: tuple[str, ...] = ()
    evidence: str = ""


@dataclass(frozen=True)
class RunEvidence:
    market_currency: str
    betsson_before: Money | None
    betsson_after: Money | None
    betsson_evidence: tuple[str, ...]
    screen_before: ScreenSnapshot
    screen_after: ScreenSnapshot
    motion: MotionSummary
    network: NetworkSummary | None
    events: GameEventsSummary | None = None
    market_language: str = "es"
