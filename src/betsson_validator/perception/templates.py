"""Localiza un control del juego por su aspecto, en cualquier parte de la pantalla y tamaño.

Así el programa no depende de dónde estaba el botón: si el proveedor lo mueve o cambia la
resolución, se sigue encontrando. Si ni siquiera se parece, el aprendizaje con IA lo reaprende.
"""

from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

Image = npt.NDArray[np.uint8]

DEFAULT_SCALES = tuple(float(s) for s in np.linspace(0.6, 1.6, 21))
DEFAULT_THRESHOLD = 0.8


@dataclass(frozen=True)
class TemplateMatch:
    x: int
    y: int
    width: int
    height: int
    score: float
    scale: float

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2


def _gray(image: Image) -> Image:
    if image.ndim == 2:  # noqa: PLR2004 - imagen ya en escala de grises
        return image
    return np.asarray(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), dtype=np.uint8)


def find_template(
    image: Image,
    template: Image,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    scales: tuple[float, ...] = DEFAULT_SCALES,
) -> TemplateMatch | None:
    """Mejor coincidencia multiescala (correlación normalizada) o None si no supera el umbral."""
    haystack = _gray(image)
    needle = _gray(template)
    best: TemplateMatch | None = None
    for scale in scales:
        width = round(needle.shape[1] * scale)
        height = round(needle.shape[0] * scale)
        if width < 8 or height < 8 or width > haystack.shape[1] or height > haystack.shape[0]:  # noqa: PLR2004
            continue
        resized = cv2.resize(needle, (width, height), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(haystack, resized, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(result)
        if best is None or score > best.score:
            best = TemplateMatch(x, y, width, height, float(score), scale)
    if best is None or best.score < threshold:
        return None
    return best


def crop(image: Image, box: tuple[int, int, int, int]) -> Image:
    """Recorta (x, y, ancho, alto) acotado a la imagen."""
    x, y, width, height = box
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + width, image.shape[1]), min(y + height, image.shape[0])
    return image[y0:y1, x0:x1].copy()
