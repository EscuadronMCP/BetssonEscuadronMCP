"""Sonda de accesibilidad: qué expone el juego a las tecnologías de apoyo (diagnóstico opcional).

Se activa con `run --ax-probe`. Toma el árbol ARIA del marco del juego antes y después de girar,
en la misma sesión y sin acciones extra. Los juegos suelen dibujarse en un canvas, así que un
árbol casi vacío es un resultado esperable y válido: lo que se busca es medirlo. No es un testigo
ni cambia ningún veredicto (y no se cuenta como fuente independiente del OCR). Solo mira el marco
del juego, nunca los formularios de la web, y guarda roles y nombres acotados.
"""

import re
from dataclasses import dataclass, field

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import FrameLocator

_NODE = re.compile(r'^\s*-\s+(?P<role>[a-z]+)(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?')
MAX_NAMES = 40
MAX_NAME_CHARS = 80
TIMEOUT_MS = 5000


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


def probe(frame: FrameLocator, phase: str) -> AccessibilityProbe:
    """Árbol ARIA del marco del juego; un fallo queda como estado "error", nunca rompe la prueba."""
    try:
        snapshot = frame.locator("body").aria_snapshot(timeout=TIMEOUT_MS)
    except PlaywrightError as error:
        return AccessibilityProbe(phase, "error", detail=type(error).__name__)
    return summarize_aria(phase, snapshot)
