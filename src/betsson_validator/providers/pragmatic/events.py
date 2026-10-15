"""Interpreta los eventos que los juegos de Pragmatic Play envían al casino (postMessage).

Formato comprobado en betsson.es el 15/10 (Sweet Bonanza 2500):
- Ronda: gameRoundStart/gameRoundStarted → spinStarted/spinEnded (uno por cascada) →
  gameRoundEnded/balanceChanged/resultShown, con betAmount, winAmount, balanceBefore,
  balanceAfter y lang.
- Saldo: {"event": "updateBalance", "params": {"total": {"currency": "€", "amount": 0}}} y
  {"event": "visualBalanceUpdate", "params": {"currency": "€", "newAmount": …}}.
- Saldo insuficiente: name "balanceTooLow" y ninguna ronda iniciada.
"""

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from betsson_validator.domain.parsing import detect_currency
from betsson_validator.scenarios.evidence import GameEventsSummary

_ROUND_START = {"gameRoundStart", "gameRoundStarted"}
_ROUND_END = {"gameRoundEnded"}
_LOW_BALANCE = {"balanceTooLow"}
_LOADING_ENDED = "gameLoadingEnded"


def loading_finished(events: Sequence[dict[str, Any]]) -> bool:
    """El juego anunció que terminó de cargar (antes de eso no tiene sentido mirar su HUD)."""
    return any(event.get("name") == _LOADING_ENDED for event in events)


def _decimal(value: Any) -> Decimal | None:  # noqa: ANN401 - valor JSON arbitrario
    """Importe de un campo JSON; None si no es un número finito (NaN e Infinity no valen)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        return None
    return number if number.is_finite() else None


def _currency(params: Any) -> str | None:  # noqa: ANN401 - valor JSON arbitrario
    if not isinstance(params, dict):
        return None
    total = params.get("total")
    symbol = params.get("currency") or (total.get("currency") if isinstance(total, dict) else None)
    return detect_currency(str(symbol)) if symbol else None


def _indexes(names: list[str], wanted: set[str]) -> list[int]:
    return [i for i, name in enumerate(names) if name in wanted]


def _anomalies(events: Sequence[dict[str, Any]], names: list[str]) -> list[str]:
    """Incoherencias del canal que impiden fiarse de él como testigo."""
    found: list[str] = []
    starts, ends = _indexes(names, _ROUND_START), _indexes(names, _ROUND_END)
    # Un mismo mensaje repetido no es otra ronda: se cuentan los fines distintos.
    distinct_ends = {json.dumps(events[i], sort_keys=True, default=str) for i in ends}
    if len(distinct_ends) > 1:
        found.append(f"{len(distinct_ends)} rondas terminadas en una sola tirada")
    if ends and (not starts or ends[-1] < starts[0]):
        found.append("la ronda terminó sin haber empezado")
    bets = {
        bet for i in (*starts, *ends) if (bet := _decimal(events[i].get("betAmount"))) is not None
    }
    if len(bets) > 1:
        found.append(f"apuestas distintas en la misma ronda: {sorted(bets)}")
    return found


def summarize_events(events: Sequence[dict[str, Any]], evidence: str = "") -> GameEventsSummary:
    names = [str(e.get("name", "")) for e in events]
    starts, ends = _indexes(names, _ROUND_START), _indexes(names, _ROUND_END)
    started = events[starts[0]] if starts else None
    ended = events[ends[-1]] if ends else None
    languages = {str(e["lang"]).lower() for e in events if e.get("lang")}
    currencies = {code for e in events if (code := _currency(e.get("params")))}
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
        anomalies=tuple(_anomalies(events, names)),
        evidence=evidence,
    )
