"""Testigos de una ejecución: los vincula al juego y les pregunta lo que el ejecutor necesita.

- Qué marco es el juego (el iframe del lanzador de Betsson) y qué orígenes tiene su árbol.
- Cuándo ha cerrado la ronda (cascadas, cobro del premio) según el servidor y los eventos.
- Qué comunicó el juego durante la tirada, solo desde sus orígenes, con las anomalías.

El ejecutor orquesta; aquí está lo que depende de los testigos (responsabilidad única).
"""

import time
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Frame

from betsson_validator.casino.betsson import GAME_FRAME_SELECTOR, BetssonCasino
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.events import (
    GameEventRecorder,
    authorized_events,
    capture_anomalies,
    payloads,
)
from betsson_validator.providers.registry import EventsInterpreter, NetworkWitness
from betsson_validator.scenarios.evidence import GameEventsSummary

ROUND_CLOSE_TIMEOUT_S = 30


@dataclass(frozen=True)
class Witnesses:
    """Testigos del proveedor disponibles en esta ejecución (pueden no existir)."""

    network: NetworkWitness | None
    events: EventsInterpreter | None


def find_game_frame(casino: BetssonCasino) -> Frame | None:
    """Marco del juego según el navegador (el iframe del lanzador de Betsson)."""
    try:
        element = casino.page.locator(GAME_FRAME_SELECTOR).element_handle(timeout=5_000)
        return element.content_frame() if element else None
    except PlaywrightError:
        return None


def frame_origins(frame: Frame) -> frozenset[str]:
    """Orígenes web del marco y de todos sus descendientes."""
    origins: set[str] = set()
    pending = [frame]
    while pending:
        current = pending.pop()
        parts = urlsplit(current.url)
        if parts.scheme in {"http", "https"}:
            origins.add(f"{parts.scheme}://{parts.netloc}")
        pending.extend(current.child_frames)
    return frozenset(origins)


def wait_round_closed(
    casino: BetssonCasino, witnesses: Witnesses, mark: int, events_mark: int
) -> bool | None:
    """Espera a que el servidor y los eventos den la ronda por cerrada (cascadas, cobro del
    premio) antes de la lectura final. Solo orienta CUÁNDO leer: la prueba sigue siendo lo que
    ve el jugador. None si no hay testigos que lo indiquen; False si se agotó la espera."""
    if witnesses.network is None and witnesses.events is None:
        return None
    deadline = time.monotonic() + ROUND_CLOSE_TIMEOUT_S
    while True:
        open_round = False
        if witnesses.events is not None:
            recorded = payloads(GameEventRecorder.collect(casino.page)[events_mark:])
            summary = witnesses.events.summarize(recorded, "")
            open_round |= summary.round_started and not summary.round_ended
        if witnesses.network is not None:
            network = witnesses.network.summarize(mark, "")
            open_round |= network.wager_accepted is not None and not network.settled
        if not open_round:
            return True
        if time.monotonic() > deadline:
            return False
        casino.page.wait_for_timeout(500)


def events_summary(
    casino: BetssonCasino,
    interpreter: EventsInterpreter | None,
    origins: frozenset[str],
    events_mark: int,
    files: EvidenceRecorder,
) -> GameEventsSummary | None:
    """Eventos del juego durante la tirada, solo de sus orígenes, con las anomalías de captura."""
    if interpreter is None:
        return None
    captured = GameEventRecorder.collect(casino.page)[events_mark:]
    game_events, foreign = authorized_events(captured, origins)
    events_file = files.save_json("eventos_del_juego", captured)
    summary = interpreter.summarize(payloads(game_events), str(events_file))
    problems = capture_anomalies(game_events, GameEventRecorder.dropped(casino.page))
    if foreign:
        seen = ", ".join(sorted({str(e.get("origin")) for e in foreign}))
        problems = (*problems, f"{len(foreign)} eventos de un origen no autorizado ({seen})")
    if problems:
        summary = replace(summary, anomalies=(*summary.anomalies, *problems))
    return summary
