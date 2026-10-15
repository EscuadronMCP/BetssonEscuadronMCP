"""Evidencias de una ejecución: capturas numeradas y archivos auxiliares en una carpeta."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

# JPEG al 85 %: ~8 veces más ligero que PNG y el texto del HUD sigue legible en el informe.
JPEG_QUALITY = 85


class EvidenceRecorder:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    @property
    def directory(self) -> Path:
        return self._directory

    def save_image(self, name: str, image: npt.NDArray[np.uint8]) -> Path:
        self._counter += 1
        path = self._directory / f"{self._counter:02d}_{name}.jpg"
        cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return path

    def save_json(self, name: str, data: Any) -> Path:  # noqa: ANN401 - datos serializables arbitrarios
        path = self._directory / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), "utf-8")
        return path
