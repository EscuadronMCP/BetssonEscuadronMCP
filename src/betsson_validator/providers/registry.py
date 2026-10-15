"""Testigos específicos de cada proveedor, elegidos por nombre desde config/providers/.

Añadir los testigos de un proveedor nuevo es implementar estos protocolos y registrarlos aquí:
el ejecutor no conoce a ningún proveedor concreto.
"""

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from playwright.sync_api import BrowserContext, Frame

from betsson_validator.providers.pragmatic.events import loading_finished, summarize_events
from betsson_validator.providers.pragmatic.recorder import GameServiceRecorder
from betsson_validator.scenarios.evidence import GameEventsSummary, NetworkSummary


class NetworkWitness(Protocol):
    """Observa el tráfico del juego con su servidor, sin modificarlo."""

    def bind(self, game_frame: Frame) -> None: ...

    def mark(self) -> int: ...

    def redacted_log(self) -> list[dict[str, str]]: ...

    def summarize(self, mark: int, evidence: str) -> NetworkSummary: ...


class EventsInterpreter(Protocol):
    """Interpreta los mensajes postMessage que el juego envía al casino."""

    def loading_finished(self, events: Sequence[dict[str, Any]]) -> bool: ...

    def summarize(self, events: Sequence[dict[str, Any]], evidence: str) -> GameEventsSummary: ...


class _PragmaticEvents:
    def loading_finished(self, events: Sequence[dict[str, Any]]) -> bool:
        return loading_finished(events)

    def summarize(self, events: Sequence[dict[str, Any]], evidence: str) -> GameEventsSummary:
        return summarize_events(events, evidence)


_NETWORK: dict[str, Callable[[BrowserContext], NetworkWitness]] = {
    "pragmatic": GameServiceRecorder,
}
_EVENTS: dict[str, EventsInterpreter] = {"pragmatic": _PragmaticEvents()}


class UnknownWitnessError(ValueError):
    pass


def network_witness(name: str | None, context: BrowserContext) -> NetworkWitness | None:
    if name is None:
        return None
    if name not in _NETWORK:
        raise UnknownWitnessError(f"Testigo de red desconocido '{name}': {sorted(_NETWORK)}")
    return _NETWORK[name](context)


def events_interpreter(name: str | None) -> EventsInterpreter | None:
    if name is None:
        return None
    if name not in _EVENTS:
        raise UnknownWitnessError(f"Intérprete de eventos desconocido '{name}': {sorted(_EVENTS)}")
    return _EVENTS[name]
