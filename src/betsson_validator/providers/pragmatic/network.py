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
    """Una tirada completa según el servidor del juego.

    `wager_accepted` sale de la respuesta del servidor (c x l que devuelve); la petición del
    cliente sola no prueba que la apuesta se aceptara. `declared_win` es el premio total que el
    servidor declara (tw), independiente de la diferencia de saldos.
    """

    wager_requested: Decimal | None
    wager_accepted: Decimal | None
    declared_win: Decimal | None
    balance_after: Decimal | None
    settled: bool
    calls: int


class NoSpinObservedError(ValueError):
    pass


def _decimal(fields: dict[str, str], key: str) -> Decimal | None:
    """Importe de un campo; None si falta, no es un número o no es finito (NaN, Infinity)."""
    try:
        value = Decimal(fields[key])
    except (KeyError, ArithmeticError):
        return None
    return value if value.is_finite() else None


def _wager(fields: dict[str, str]) -> Decimal | None:
    coin, lines = _decimal(fields, "c"), _decimal(fields, "l")
    return None if coin is None or lines is None else coin * lines


def summarize_round(calls: Sequence[GameServiceCall]) -> SpinRound:
    """Resume la tirada a partir del primer doSpin y de las llamadas que lo siguen."""
    start = next((i for i, c in enumerate(calls) if c.action == "doSpin"), None)
    if start is None:
        raise NoSpinObservedError("No se observó ninguna petición doSpin.")
    round_calls = calls[start:]
    first, last = round_calls[0], round_calls[-1]
    wins = [win for c in round_calls if (win := _decimal(c.response, "tw")) is not None]
    accepted = _wager(first.response) if "balance" in first.response else None
    return SpinRound(
        wager_requested=_wager(first.request),
        wager_accepted=accepted,
        declared_win=max(wins) if wins else None,
        balance_after=_decimal(last.response, "balance"),
        settled=accepted is not None and _is_settled(last),
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
