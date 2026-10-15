"""Sonda de accesibilidad: qué expone el juego a las tecnologías de apoyo (diagnóstico opcional).

Se activa con `run --ax-probe`. Toma el árbol ARIA del marco del juego antes y después de girar,
en la misma sesión y sin acciones extra. Los juegos suelen dibujarse en un canvas, así que un
árbol casi vacío es un resultado esperable y válido: lo que se busca es medirlo. No es un testigo
ni cambia ningún veredicto (y no se cuenta como fuente independiente del OCR). Solo mira el marco
del juego, nunca los formularios de la web, y guarda roles y nombres acotados.
"""

import re
from dataclasses import dataclass, field, replace

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import FrameLocator

_NODE = re.compile(r'^\s*-\s+(?P<role>[a-z]+)(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?')
MAX_NAMES = 40
MAX_NAME_CHARS = 80
TIMEOUT_MS = 5000
MAX_FRAME_DEPTH = 3  # el lanzador de Betsson envuelve el juego en otro marco


@dataclass(frozen=True)
class AccessibilityProbe:
    phase: str
    status: str  # "con datos", "vacío" o "error"
    nodes: int = 0
    roles: dict[str, int] = field(default_factory=dict)
    names: tuple[str, ...] = ()
    detail: str = ""


def summarize_aria(phase: str, snapshot: str) -> AccessibilityProbe:
    """Cuenta roles y recoge nombres visibles (acotados) de un árbol ARIA en YAML."""
    roles: dict[str, int] = {}
    names: list[str] = []
    for line in snapshot.splitlines():
        match = _NODE.match(line)
        if match is None:
            continue
        roles[match["role"]] = roles.get(match["role"], 0) + 1
        if match["name"] and len(names) < MAX_NAMES:
            names.append(match["name"][:MAX_NAME_CHARS])
    nodes = sum(roles.values())
    return AccessibilityProbe(phase, "con datos" if nodes else "vacío", nodes, roles, tuple(names))


def probe(frame: FrameLocator, phase: str, *, settled: bool = True) -> AccessibilityProbe:
    """Árbol ARIA del juego. El juego vive en un marco anidado (el árbol ARIA no atraviesa
    marcos): mientras el marco tenga iframes se baja al más grande, que es el del juego, aunque
    haya otros controles al lado. Un fallo queda como estado "error", nunca rompe la prueba."""
    current = frame
    for depth in range(1, MAX_FRAME_DEPTH + 1):
        try:
            child = _largest_iframe(current) if depth < MAX_FRAME_DEPTH else None
            if child is not None:
                current = current.frame_locator("iframe").nth(child)
                continue
            snapshot = current.locator("body").aria_snapshot(timeout=TIMEOUT_MS)
        except PlaywrightError as error:
            return AccessibilityProbe(
                phase, "error", detail=f"{type(error).__name__} en el marco de nivel {depth}"
            )
        note = "" if settled else "; tomada con el marcador aún sin estabilizar"
        return replace(summarize_aria(phase, snapshot), detail=f"marco de nivel {depth}{note}")
    return AccessibilityProbe(phase, "error", detail="sin marco")


def _largest_iframe(frame: FrameLocator) -> int | None:
    """Índice del iframe más grande del marco (el juego), o None si no tiene ninguno."""
    iframes = frame.locator("iframe")
    best: tuple[float, int] | None = None
    for index in range(iframes.count()):
        box = iframes.nth(index).bounding_box(timeout=TIMEOUT_MS)
        area = box["width"] * box["height"] if box else 0.0
        if best is None or area > best[0]:
            best = (area, index)
    return best[1] if best is not None else None
