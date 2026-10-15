"""Graba los mensajes que el juego envía a la página del casino (window.postMessage).

Es el canal de integración entre el juego del proveedor y Betsson: el juego avisa de que una
ronda empieza o termina, de la apuesta, del premio, del saldo, del idioma… No es la pantalla ni
el tráfico de red: es una capa distinta del navegador, y por eso un testigo independiente.

El grabador es genérico (cualquier proveedor); cada proveedor interpreta sus propios eventos.
Solo se aceptan mensajes cuyo emisor es el marco del juego (o un marco dentro de él): así un
anuncio, el servicio antifraude o cualquier otra ventana no pueden hacerse pasar por el juego.
En betsson.es ese marco vive dentro de un shadow DOM, por eso se busca también ahí.
Cada evento conserva su origen y su hora de llegada como evidencia.
"""

import json
from typing import Any

from playwright.sync_api import BrowserContext, Page

_LISTENER = """
((frameSelector) => {
  if (window.top !== window || window.__gameEvents) return;
  window.__gameEvents = [];
  const find = (root) => {
    const direct = root.querySelector(frameSelector);
    if (direct) return direct;
    for (const element of root.querySelectorAll('*')) {
      const found = element.shadowRoot && find(element.shadowRoot);
      if (found) return found;
    }
    return null;
  };
  let cached = null;
  const gameFrame = () => (cached && cached.isConnected ? cached : (cached = find(document)));
  const fromGame = (source) => {
    const frame = gameFrame();
    for (let w = source; frame && w; w = (w === w.parent ? null : w.parent)) {
      if (w === frame.contentWindow) return true;
      if (w === window) return false;
    }
    return false;
  };
  window.addEventListener('message', (e) => {
    if (e.origin === location.origin || !fromGame(e.source)) return;
    let data = e.data;
    if (typeof data === 'string') { try { data = JSON.parse(data); } catch (err) { return; } }
    if (!data || typeof data !== 'object' || !(('name' in data) || ('event' in data))) return;
    try {
      const copy = JSON.parse(JSON.stringify(data));
      window.__gameEvents.push({t: Date.now(), origin: e.origin, data: copy});
    } catch (err) { /* no serializable */ }
  });
})(__FRAME_SELECTOR__);
"""

GameEvent = dict[str, Any]


class GameEventRecorder:
    def __init__(self, context: BrowserContext, game_frame_selector: str) -> None:
        context.add_init_script(
            _LISTENER.replace("__FRAME_SELECTOR__", json.dumps(game_frame_selector))
        )

    @staticmethod
    def collect(page: Page) -> list[GameEvent]:
        """Eventos recibidos (hora, origen y contenido); se pierden al navegar: leer antes."""
        raw = page.evaluate("window.__gameEvents || []")
        return [
            event
            for event in raw
            if isinstance(event, dict) and isinstance(event.get("data"), dict)
        ]


def payloads(events: list[GameEvent]) -> list[dict[str, Any]]:
    """Solo el contenido de cada evento, que es lo que interpreta cada proveedor."""
    return [event["data"] for event in events]
