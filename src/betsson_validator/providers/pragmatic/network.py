"""Testigo de red de Pragmatic Play: interpreta el tráfico de gameService (solo observado).

Formato comprobado en betsson.es el 15/10 (Sweet Bonanza 2500):
- Petición y respuesta en `k=v&k=v`. `action`: doInit, doSpin, doCollect.
- El primer doSpin de una tirada cobra la apuesta (`c` x `l`) y devuelve `balance` ya descontado.
- Las cascadas generan doSpin de continuación que no cobran.
- `na=c` significa que falta cobrar el premio; el doCollect posterior devuelve `na=s` y el saldo
  definitivo. La tirada está liquidada cuando la última respuesta trae `na=s`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import parse_qsl

GAME_SERVICE_PATH = "/gameService"
_SENSITIVE = re.compile(
    r"(mgckey|token|ssid|SESSION|sessionId|AUTHTOKEN)([=@~:\"]+)[^&`~ \",]*", re.IGNORECASE
)
_SETTLED = "s"
_TUMBLE_KEYS = ("rs_p", "rs_c", "rs_m")


def redact(text: str) -> str:
    """Oculta tokens de sesión antes de guardar tráfico en evidencias o logs."""
    return _SENSITIVE.sub(r"\1\2<REDACTED>", text)


def parse_fields(body: str) -> dict[str, str]:
    return dict(parse_qsl(body, keep_blank_values=True))


@dataclass(frozen=True)
class GameServiceCall:
    request: dict[str, str]
    response: dict[str, str]

    @property
    def action(self) -> str:
        return self.request.get("action", "")

    @classmethod
    def from_bodies(cls, request_body: str, response_body: str) -> "GameServiceCall":
        return cls(parse_fields(request_body), parse_fields(response_body))


@dataclass(frozen=True)
class SpinRound:
    """Una tirada completa según el servidor del juego."""

    balance_before: Decimal
    wager: Decimal
    balance_after: Decimal
    total_win: Decimal
    settled: bool
    calls: int

    @property
    def payout(self) -> Decimal:
        """Premio abonado deducido del saldo: después - (antes - apuesta)."""
        return self.balance_after - (self.balance_before - self.wager)


class NoSpinObservedError(ValueError):
    pass


def _decimal(fields: dict[str, str], key: str) -> Decimal:
    return Decimal(fields[key])


def summarize_round(calls: Sequence[GameServiceCall], balance_before: Decimal) -> SpinRound:
    """Resume la tirada a partir del primer doSpin y de las llamadas que lo siguen."""
    start = next((i for i, c in enumerate(calls) if c.action == "doSpin"), None)
    if start is None:
        raise NoSpinObservedError("No se observó ninguna petición doSpin.")
    round_calls = calls[start:]
    first = round_calls[0]
    wager = _decimal(first.request, "c") * _decimal(first.request, "l")
    last = round_calls[-1]
    wins = [_decimal(c.response, "tw") for c in round_calls if "tw" in c.response]
    return SpinRound(
        balance_before=balance_before,
        wager=wager,
        balance_after=_decimal(last.response, "balance"),
        total_win=max(wins, default=Decimal("0")),
        settled=_is_settled(last),
        calls=len(round_calls),
    )


def _is_settled(last: GameServiceCall) -> bool:
    if last.response.get("na") != _SETTLED:
        return False
    if last.action == "doCollect":
        return True
    return not any(key in last.response for key in _TUMBLE_KEYS)


def balance_from_init(calls: Sequence[GameServiceCall]) -> Decimal | None:
    """Saldo que el servidor del juego comunicó antes de la tirada (último doInit/doCollect)."""
    for call in reversed(calls):
        if call.action in {"doInit", "doCollect"} and "balance" in call.response:
            return _decimal(call.response, "balance")
    return None
