"""Aprendizaje de la pantalla de un juego desconocido con una IA de visión.

Se usa SOLO para incorporar un juego nuevo o reparar un perfil que ha dejado de encajar; las
ejecuciones normales son locales y no llaman a la IA. Lo que propone la IA no se da por bueno:
quien lo usa lo valida con OCR y con la reacción del juego (ver profiles.py y game/player.py).
"""

import base64
from typing import Protocol

import cv2
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

Image = npt.NDArray[np.uint8]

# Modelo suficiente para localizar botones y leer etiquetas, al menor coste
# (≈ 0,002 $ por captura). Si su propuesta no supera la validación, se reintenta con FALLBACK.
DEFAULT_MODEL = "claude-haiku-5-5"
FALLBACK_MODEL = "claude-sonnet-5-5"


class Box(BaseModel):
    """Rectángulo en píxeles de la captura enviada, con origen arriba a la izquierda."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height


class ScreenAnalysis(BaseModel):
    is_intro_screen: bool = Field(
        description="True si es una pantalla de bienvenida previa al juego (aún sin crédito)."
    )
    continue_button: Box | None = Field(
        description="Botón para pasar la pantalla de bienvenida; null si no es una."
    )
    spin_button: Box | None = Field(description="Botón principal para girar; null si no se ve.")
    bet_decrease_button: Box | None = Field(
        description="Botón que reduce la apuesta (normalmente '-'); null si no se ve."
    )
    bet_increase_button: Box | None = Field(
        description="Botón que aumenta la apuesta (normalmente '+'); null si no se ve."
    )
    reels_area: Box | None = Field(
        description="Zona donde giran los rodillos o símbolos del juego; null si no se ve."
    )
    credit_label: str | None = Field(
        description="Texto exacto de la etiqueta junto al saldo del jugador (p. ej. 'CRÉDITO')."
    )
    bet_label: str | None = Field(
        description="Texto exacto de la etiqueta junto a la apuesta actual (p. ej. 'APUESTA')."
    )
    win_label: str | None = Field(
        description="Texto exacto de la etiqueta junto al premio, si se ve (p. ej. 'GANANCIA')."
    )
    message_text: str | None = Field(
        description="Texto completo de cualquier mensaje o diálogo superpuesto, si lo hay."
    )


class ScreenLearner(Protocol):
    @property
    def cost_usd(self) -> float:
        """Coste acumulado de las llamadas a la IA (para el informe y el control de gasto)."""
        ...

    def analyze(self, image: Image, *, model: str | None = None) -> ScreenAnalysis: ...


# Precio por millón de tokens (entrada, salida) en USD, tarifas de la API a 15/10/2026.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


_PROMPT = """Esta imagen es una captura ({width}x{height} px) de un juego de tragaperras online \
tal y como lo ve el jugador. Localiza los controles y etiquetas que se piden. Las cajas van en \
píxeles de ESTA imagen (origen arriba a la izquierda) y deben ajustarse al control visible, sin \
margen extra. Copia las etiquetas exactamente como aparecen escritas (mayúsculas y acentos \
incluidos). Si algo no se ve, devuelve null: no lo inventes."""


class LearnerError(RuntimeError):
    pass


class ClaudeScreenLearner:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        import anthropic  # noqa: PLC0415 - solo se carga si de verdad hay que aprender

        self._client = anthropic.Anthropic()
        self._model = model
        self._cost_usd = 0.0
        self.calls: list[dict[str, object]] = []

    @property
    def cost_usd(self) -> float:
        return self._cost_usd

    def analyze(self, image: Image, *, model: str | None = None) -> ScreenAnalysis:
        ok, png = cv2.imencode(".png", image)
        if not ok:
            raise LearnerError("No se pudo codificar la captura.")
        height, width = image.shape[:2]
        response = self._client.messages.parse(
            model=model or self._model,
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.standard_b64encode(png.tobytes()).decode(),
                            },
                        },
                        {"type": "text", "text": _PROMPT.format(width=width, height=height)},
                    ],
                }
            ],
            output_format=ScreenAnalysis,
        )
        used = model or self._model
        price_in, price_out = PRICES_PER_MTOK.get(used, (0.0, 0.0))
        cost = (
            response.usage.input_tokens * price_in + response.usage.output_tokens * price_out
        ) / 1_000_000
        self._cost_usd += cost
        self.calls.append(
            {
                "model": used,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cost_usd": round(cost, 6),
            }
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise LearnerError(f"La IA no devolvió un análisis válido ({response.stop_reason}).")
        return response.parsed_output
