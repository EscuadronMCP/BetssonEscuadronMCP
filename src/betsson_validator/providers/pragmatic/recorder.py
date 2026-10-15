"""Graba el tráfico gameService del juego sin modificarlo (observación pasiva).

Solo cuenta el tráfico que pide el propio juego: en cuanto el juego está abierto, el grabador se
vincula a su marco (`bind`) y desde entonces solo admite peticiones de ese marco o de sus
descendientes; lo grabado antes de vincularlo se filtra igual. La página del casino, otros
marcos (anuncios, antifraude) o un service worker no son el juego. También lleva la salud de la
captura: respuestas ilegibles y tráfico descartado, con el motivo, para poder diagnosticarlo.
"""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class _Entry:
    frame: Frame
    call: GameServiceCall | None  # None: respuesta ilegible (error HTTP, vacía, otro esquema)
    redacted: dict[str, str]


class GameServiceRecorder:
    def __init__(self, context: BrowserContext) -> None:
        self._entries: list[_Entry] = []
        self._game_frame: Frame | None = None
        self.ignored: list[str] = []  # motivo de cada respuesta gameService descartada
        context.on("response", self._on_response)

    def bind(self, game_frame: Frame) -> None:
        """Vincula el grabador al marco del juego y descarta lo que no venía de él."""
        self._game_frame = game_frame
        kept = [entry for entry in self._entries if _within(entry.frame, game_frame)]
        self.ignored += ["no venía del marco del juego"] * (len(self._entries) - len(kept))
        self._entries = kept

    def _on_response(self, response: Response) -> None:
        if GAME_SERVICE_PATH not in response.url:
            return
        try:
            frame = response.request.frame
        except Exception:  # p. ej. una petición de un service worker: no es del juego
            self.ignored.append("sin marco de origen")
            return
        if frame.parent_frame is None:
            self.ignored.append("pedida por la página del casino, no por el juego")
            return
        if self._game_frame is not None and not _within(frame, self._game_frame):
            self.ignored.append("no venía del marco del juego")
            return
        try:
            request_body = response.request.post_data or ""
            response_body = response.text() if response.ok else ""
        except Exception:  # una respuesta ilegible no debe tumbar la prueba, pero se anota
            response_body = ""
        call = GameServiceCall.from_bodies(request_body, response_body)
        readable = bool(call.response) and "balance" in call.response
        redacted = {"request": redact(request_body), "response": redact(response_body)}
        self._entries.append(_Entry(frame, call if readable else None, redacted))

    def mark(self) -> int:
        """Posición actual: permite quedarse solo con las llamadas posteriores a un momento."""
        return len(self._entries)

    def redacted_log(self) -> list[dict[str, str]]:
        """Tráfico sin tokens de sesión, apto para guardarse como evidencia."""
        ignored = [{"descartado": reason} for reason in self.ignored]
        return [*(entry.redacted for entry in self._entries), *ignored]

    def summarize(self, mark: int, evidence: str) -> NetworkSummary:
        """Lo que dijo el servidor sobre la tirada que empezó en `mark`."""
        before = [e.call for e in self._entries[:mark] if e.call is not None]
        during_entries = self._entries[mark:]
        during = [e.call for e in during_entries if e.call is not None]
        observed = sum(1 for e in self._entries if e.call is not None)
        unreadable = sum(1 for e in during_entries if e.call is None)
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


def _within(frame: Frame | None, root: Frame) -> bool:
    """El marco es el del juego o uno de sus descendientes."""
    current = frame
    while current is not None:
        if current == root:
            return True
        current = current.parent_frame
    return False
