"""Graba el tráfico gameService del juego sin modificarlo (observación pasiva)."""

from playwright.sync_api import BrowserContext, Response

from betsson_validator.providers.pragmatic.network import (
    GAME_SERVICE_PATH,
    GameServiceCall,
    redact,
)


class GameServiceRecorder:
    def __init__(self, context: BrowserContext) -> None:
        self._calls: list[GameServiceCall] = []
        self._redacted: list[dict[str, str]] = []
        context.on("response", self._on_response)

    def _on_response(self, response: Response) -> None:
        if GAME_SERVICE_PATH not in response.url:
            return
        try:
            request_body = response.request.post_data or ""
            response_body = response.text()
        except Exception:  # una respuesta ilegible no debe tumbar la prueba
            return
        self._calls.append(GameServiceCall.from_bodies(request_body, response_body))
        self._redacted.append({"request": redact(request_body), "response": redact(response_body)})

    @property
    def calls(self) -> list[GameServiceCall]:
        return list(self._calls)

    def mark(self) -> int:
        """Posición actual: permite quedarse solo con las llamadas posteriores a un momento."""
        return len(self._calls)

    def calls_since(self, mark: int) -> list[GameServiceCall]:
        return self._calls[mark:]

    def redacted_log(self) -> list[dict[str, str]]:
        """Tráfico sin tokens de sesión, apto para guardarse como evidencia."""
        return list(self._redacted)
