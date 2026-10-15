"""Graba el tráfico gameService del juego sin modificarlo (observación pasiva).

Solo cuenta el tráfico que el propio juego pide a su servidor: peticiones hechas desde un marco
incrustado (no la página del casino) del mismo sitio que el servidor (p. ej. el juego en
`a.proveedor.net` y su servidor en `b.proveedor.net`). También se lleva la salud de la captura:
respuestas ilegibles y tráfico descartado, con el motivo, para poder diagnosticarlo.
"""

from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Frame, Response

from betsson_validator.providers.pragmatic.network import (
    GAME_SERVICE_PATH,
    GameServiceCall,
    NoSpinObservedError,
    balance_from_init,
    redact,
    summarize_round,
)
from betsson_validator.scenarios.evidence import NetworkSummary


class GameServiceRecorder:
    def __init__(self, context: BrowserContext) -> None:
        self._calls: list[GameServiceCall] = []
        self._redacted: list[dict[str, str]] = []
        # Posición (número de llamadas ya grabadas) de cada respuesta que no se pudo leer.
        self._unreadable_at: list[int] = []
        self.ignored: list[str] = []  # motivo de cada respuesta gameService descartada
        context.on("response", self._on_response)

    def _on_response(self, response: Response) -> None:
        if GAME_SERVICE_PATH not in response.url:
            return
        reason = _foreign_reason(response)
        if reason is not None:
            self.ignored.append(reason)
            return
        try:
            request_body = response.request.post_data or ""
            response_body = response.text() if response.ok else ""
        except Exception:  # una respuesta ilegible no debe tumbar la prueba, pero se anota
            response_body = ""
        call = GameServiceCall.from_bodies(request_body, response_body)
        if not call.response or "balance" not in call.response:
            # Error HTTP, cuerpo vacío o sin el esquema del juego: no prueba nada.
            self._unreadable_at.append(len(self._calls))
            return
        self._calls.append(call)
        self._redacted.append({"request": redact(request_body), "response": redact(response_body)})

    def mark(self) -> int:
        """Posición actual: permite quedarse solo con las llamadas posteriores a un momento."""
        return len(self._calls)

    def redacted_log(self) -> list[dict[str, str]]:
        """Tráfico sin tokens de sesión, apto para guardarse como evidencia."""
        ignored = [{"descartado": reason} for reason in self.ignored]
        return [*self._redacted, *ignored]

    def summarize(self, mark: int, evidence: str) -> NetworkSummary:
        """Lo que dijo el servidor sobre la tirada que empezó en `mark`."""
        before, during = self._calls[:mark], self._calls[mark:]
        observed = len(self._calls)
        unreadable = sum(1 for at in self._unreadable_at if at >= mark)
        try:
            spin = summarize_round(during)
        except NoSpinObservedError:
            return NetworkSummary(
                spin_requested=False,
                evidence=evidence,
                observed_calls=observed,
                unreadable=unreadable,
            )
        return NetworkSummary(
            spin_requested=True,
            settled=spin.settled,
            wager_requested=spin.wager_requested,
            wager_accepted=spin.wager_accepted,
            declared_win=spin.declared_win,
            balance_before=balance_from_init(before),
            balance_after=spin.balance_after,
            evidence=evidence,
            observed_calls=observed,
            unreadable=unreadable,
        )


def _site(url: str) -> str:
    """Dominio registrable aproximado (las dos últimas etiquetas): a.x.net y b.x.net comparten."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return ""
    return ".".join((parts.hostname or "").split(".")[-2:])


def _foreign_reason(response: Response) -> str | None:
    """None si la pidió el juego; si no, el motivo (sin URL completa: puede llevar tokens)."""
    try:
        frame = response.request.frame
    except Exception:  # p. ej. una petición de un service worker
        return "sin marco de origen"
    if frame.parent_frame is None:
        return "pedida por la página del casino, no por el juego"
    site = _frame_site(frame)
    if site != _site(response.url):
        return f"marco de {site or 'origen desconocido'} distinto del servidor"
    return None


def _frame_site(frame: Frame) -> str:
    """Sitio del marco; uno sin URL propia (about:blank) hereda el de quien lo creó."""
    current: Frame | None = frame
    while current is not None:
        if site := _site(current.url):
            return site
        current = current.parent_frame
    return ""
