"""Detección del ciclo de vida de un giro a partir de la actividad visual del juego.

Un giro real produce movimiento sostenido (los rodillos girando) seguido de reposo.
Pulsar el botón sin que el juego reaccione no produce ese patrón, así que esto es una
prueba visual de que la tirada empezó y terminó, independiente del proveedor.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

Frame = npt.NDArray[np.uint8]

# Diferencia mínima por píxel (0-255) para contar como cambio: filtra ruido de compresión.
_PIXEL_DELTA = 25
_GRAYSCALE_NDIM = 2


def motion_score(previous: Frame, current: Frame) -> float:
    """Fracción de píxeles (0-1) que cambian de forma apreciable entre dos capturas."""
    if previous.shape != current.shape:
        raise ValueError(f"Capturas de tamaño distinto: {previous.shape} y {current.shape}")
    gray_previous = _to_gray(previous)
    gray_current = _to_gray(current)
    delta = cv2.absdiff(gray_previous, gray_current)
    changed = int(np.count_nonzero(delta > _PIXEL_DELTA))
    return changed / delta.size


def _to_gray(frame: Frame) -> Frame:
    if frame.ndim == _GRAYSCALE_NDIM:
        return frame
    return np.asarray(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), dtype=np.uint8)


@dataclass(frozen=True)
class MotionThresholds:
    """Umbrales ajustables por perfil de juego."""

    start: float = 0.08  # actividad mínima para considerar que el giro empezó
    still: float = 0.01  # actividad máxima para considerar la pantalla en reposo
    still_samples: int = 4  # muestras seguidas en reposo para dar el giro por terminado
    min_active_samples: int = 3  # muestras con actividad para descartar un parpadeo


DEFAULT_THRESHOLDS = MotionThresholds()

# Margen sobre la actividad de fondo medida antes de girar.
_IDLE_STILL_FACTOR = 1.5
_IDLE_STILL_MARGIN = 0.005
_IDLE_START_FACTOR = 3.0
_IDLE_START_MARGIN = 0.03


def adaptive_thresholds(
    idle_scores: Iterable[float], base: MotionThresholds = DEFAULT_THRESHOLDS
) -> MotionThresholds:
    """Umbrales relativos a la actividad de fondo del juego medida antes de girar.

    Hay juegos con animaciones continuas (personajes, burbujas) en los que la pantalla nunca
    queda del todo quieta: un umbral fijo de reposo no se cumpliría jamás. Se toma la actividad
    máxima en reposo y se exige superarla claramente para "giro" y no superarla para "reposo".
    """
    idle = max(idle_scores, default=0.0)
    still = max(base.still, idle * _IDLE_STILL_FACTOR + _IDLE_STILL_MARGIN)
    start = max(base.start, idle * _IDLE_START_FACTOR + _IDLE_START_MARGIN, still * 2)
    return MotionThresholds(
        start=start,
        still=still,
        still_samples=base.still_samples,
        min_active_samples=base.min_active_samples,
    )


@dataclass(frozen=True)
class SpinLifecycle:
    started: bool
    completed: bool
    start_index: int | None
    end_index: int | None
    peak_score: float


def detect_spin_lifecycle(
    scores: Iterable[float], thresholds: MotionThresholds = DEFAULT_THRESHOLDS
) -> SpinLifecycle:
    """Analiza la serie de actividad visual y localiza inicio y fin del giro."""
    start_index: int | None = None
    active = 0
    still_run = 0
    peak = 0.0
    for index, score in enumerate(scores):
        peak = max(peak, score)
        if start_index is None:
            if score >= thresholds.start:
                start_index = index
                active = 1
            continue
        if score >= thresholds.start:
            active += 1
        if score <= thresholds.still:
            still_run += 1
            if still_run >= thresholds.still_samples and active >= thresholds.min_active_samples:
                return SpinLifecycle(True, True, start_index, index, peak)
        else:
            still_run = 0
    started = start_index is not None and active >= thresholds.min_active_samples
    return SpinLifecycle(started, False, start_index if started else None, None, peak)
