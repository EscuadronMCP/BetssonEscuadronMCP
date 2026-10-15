"""Búsqueda de controles por imagen sobre capturas reales, incluidas interfaces alteradas.

Las alteraciones simulan lo que pasaría si el proveedor cambiara su interfaz: el botón de girar
se mueve a otra zona o cambia de tamaño. La prueba debe encontrarlo igualmente.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from betsson_validator.perception.templates import crop, find_template

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pragmaticplay"
# Botón de girar en la captura real "lista para jugar" (x, y, ancho, alto).
SPIN_BOX = (651, 415, 92, 82)


def load(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None
    return np.asarray(image, dtype=np.uint8)


@pytest.fixture(scope="module")
def ready() -> np.ndarray:
    return load("sweet_bonanza_ready.png")


@pytest.fixture(scope="module")
def spin_template(ready: np.ndarray) -> np.ndarray:
    return crop(ready, SPIN_BOX)


def test_finds_spin_button_where_it_is(ready: np.ndarray, spin_template: np.ndarray) -> None:
    match = find_template(ready, spin_template)
    assert match is not None
    assert abs(match.x - SPIN_BOX[0]) <= 3 and abs(match.y - SPIN_BOX[1]) <= 3


def test_finds_spin_button_after_it_moves(ready: np.ndarray, spin_template: np.ndarray) -> None:
    moved = ready.copy()
    x, y, w, h = SPIN_BOX
    moved[y : y + h, x : x + w] = moved[y - h : y, x : x + w]  # tapa el sitio original
    moved[40 : 40 + h, 60 : 60 + w] = spin_template  # lo pone arriba a la izquierda
    match = find_template(moved, spin_template)
    assert match is not None
    assert abs(match.x - 60) <= 3 and abs(match.y - 40) <= 3


def test_finds_spin_button_at_another_resolution(spin_template: np.ndarray) -> None:
    ready = load("sweet_bonanza_ready.png")
    bigger = np.asarray(
        cv2.resize(ready, None, fx=1.3, fy=1.3, interpolation=cv2.INTER_CUBIC), dtype=np.uint8
    )
    match = find_template(bigger, spin_template)
    assert match is not None
    assert abs(match.x - SPIN_BOX[0] * 1.3) <= 6
    assert match.scale == pytest.approx(1.3, abs=0.06)


def test_does_not_invent_a_button_that_is_not_there(spin_template: np.ndarray) -> None:
    intro = load("sweet_bonanza_insufficient_funds.png")
    without = intro.copy()
    x, y, w, h = SPIN_BOX
    without[y : y + h, x : x + w] = 0
    assert find_template(without, spin_template, threshold=0.9) is None


def test_crop_is_bounded_to_the_image(ready: np.ndarray) -> None:
    piece = crop(ready, (880, 490, 100, 100))
    assert piece.shape[0] == ready.shape[0] - 490
    assert piece.shape[1] == ready.shape[1] - 880


def test_flat_template_never_matches(ready: np.ndarray) -> None:
    flat = np.full((60, 60, 3), (0, 0, 255), dtype=np.uint8)
    assert find_template(ready, flat) is None
