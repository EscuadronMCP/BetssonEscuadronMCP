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
    currency_seen: str | None
    message: str | None
    evidence: str


@dataclass(frozen=True)
class MotionSummary:
    started: bool
    completed: bool
    samples: int
    peak: float


@dataclass(frozen=True)
class NetworkSummary:
    """Lo que dijo el servidor del juego. `spin_requested` es False si no hubo doSpin."""

    spin_requested: bool
    settled: bool = False
    wager: Decimal | None = None
    balance_before: Decimal | None = None
    balance_after: Decimal | None = None
    payout: Decimal | None = None
    evidence: str = ""


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
