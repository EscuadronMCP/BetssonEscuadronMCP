"""Lectura de texto en capturas del juego (OCR)."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class TextBox:
    """Texto reconocido y su posición (esquina superior izquierda y tamaño, en píxeles)."""

    text: str
    score: float
    x: int
    y: int
    width: int
    height: int

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2


class TextReader(Protocol):
    def read(self, image: npt.NDArray[np.uint8]) -> list[TextBox]: ...


class RapidOcrReader:
    """OCR con los modelos de PaddleOCR sobre ONNX Runtime: sin dependencias del sistema."""

    def __init__(self) -> None:
        from rapidocr import RapidOCR  # noqa: PLC0415 - carga perezosa: tarda en inicializarse
        from rapidocr.utils.output import RapidOCROutput  # noqa: PLC0415

        self._engine = RapidOCR()
        self._output_type = RapidOCROutput

    def read(self, image: npt.NDArray[np.uint8]) -> list[TextBox]:
        result = self._engine(image)
        if not isinstance(result, self._output_type):
            return []
        if result.boxes is None or result.txts is None or result.scores is None:
            return []
        boxes: list[TextBox] = []
        for box, text, score in zip(result.boxes, result.txts, result.scores, strict=True):
            xs = [int(point[0]) for point in box]
            ys = [int(point[1]) for point in box]
            boxes.append(
                TextBox(
                    text=str(text),
                    score=float(score),
                    x=min(xs),
                    y=min(ys),
                    width=max(xs) - min(xs),
                    height=max(ys) - min(ys),
                )
            )
        return boxes
