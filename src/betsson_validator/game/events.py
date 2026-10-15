"""Graba los mensajes que el juego envía a la página del casino (window.postMessage).

Es el canal de integración entre el juego del proveedor y Betsson: el juego avisa de que una
ronda empieza o termina, de la apuesta, del premio, del saldo, del idioma… No es la pantalla ni
el tráfico de red: es una capa distinta del navegador, y por eso un testigo independiente.

El grabador es genérico (cualquier proveedor); cada proveedor interpreta sus propios eventos.
Solo se guardan objetos con campo "name" o "event" que no procedan del propio casino, lo que
deja fuera, por ejemplo, los mensajes del servicio antifraude.
"""

import json
from typing import Any

from playwright.sync_api import BrowserContext, Page

_LISTENER = """
(() => {
  if (window.top !== window || window.__gameEvents) return;
  window.__gameEvents = [];
  window.addEventListener('message', (e) => {
    if (e.origin === location.origin) return;
    let data = e.data;
    if (typeof data === 'string') { try { data = JSON.parse(data); } catch (err) { return; } }
    if (!data || typeof data !== 'object' || !(('name' in data) || ('event' in data))) return;
    try {
      const copy = JSON.parse(JSON.stringify(data));
      window.__gameEvents.push({t: Date.now(), origin: e.origin, data: copy});
    } catch (err) { /* no serializable */ }
  });
})();
"""

GameEvent = dict[str, Any]


class GameEventRecorder:
    def __init__(self, context: BrowserContext) -> None:
        context.add_init_script(_LISTENER)

    @staticmethod
    def collect(page: Page) -> list[GameEvent]:
        """Eventos recibidos por la página actual (se pierden al navegar: leer antes de salir)."""
        raw = page.evaluate("window.__gameEvents || []")
        return [event["data"] for event in raw if isinstance(event.get("data"), dict)]


def dumps(events: list[GameEvent]) -> str:
    return json.dumps(events, ensure_ascii=False, indent=1)
