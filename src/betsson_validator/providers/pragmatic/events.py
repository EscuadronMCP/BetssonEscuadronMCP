"""Interpreta los eventos que los juegos de Pragmatic Play envían al casino (postMessage).

Formato comprobado en betsson.es el 15/10 (Sweet Bonanza 2500):
- Ronda: gameRoundStart/gameRoundStarted → spinStarted/spinEnded (uno por cascada) →
  gameRoundEnded/balanceChanged/resultShown, con betAmount, winAmount, balanceBefore,
  balanceAfter y lang.
- Saldo: {"event": "updateBalance", "params": {"total": {"currency": "€", "amount": 0}}} y
  {"event": "visualBalanceUpdate", "params": {"currency": "€", "newAmount": …}}.
- Saldo insuficiente: name "balanceTooLow" y ninguna ronda iniciada.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from betsson_validator.domain.parsing import detect_currency
from betsson_validator.scenarios.evidence import GameEventsSummary

_ROUND_START = {"gameRoundStart", "gameRoundStarted"}
_ROUND_END = {"gameRoundEnded"}
_LOW_BALANCE = {"balanceTooLow"}


def _decimal(value: Any) -> Decimal | None:  # noqa: ANN401 - valor JSON arbitrario
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def summarize_events(events: Sequence[dict[str, Any]], evidence: str = "") -> GameEventsSummary:
    names = [str(e.get("name", "")) for e in events]
    started = next((e for e in events if e.get("name") in _ROUND_START), None)
    ended = next((e for e in reversed(events) if e.get("name") in _ROUND_END), None)
    languages = {str(e["lang"]).lower() for e in events if e.get("lang")}
    currencies = set()
    for event in events:
        params = event.get("params")
        if isinstance(params, dict):
            symbol = params.get("currency") or (params.get("total") or {}).get("currency")
            if symbol and (code := detect_currency(str(symbol))):
                currencies.add(code)
    return GameEventsSummary(
        received=bool(events),
        round_started=started is not None,
        round_ended=ended is not None,
        low_balance=any(name in _LOW_BALANCE for name in names),
        bet=_decimal((started or ended or {}).get("betAmount")),
        win=_decimal(ended.get("winAmount")) if ended else None,
        balance_before=_decimal(started.get("balanceBefore")) if started else None,
        balance_after=_decimal(ended.get("balanceAfter")) if ended else None,
        languages=tuple(sorted(languages)),
        currencies=tuple(sorted(currencies)),
        evidence=evidence,
    )
