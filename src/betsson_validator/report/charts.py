"""Gráfica SVG de la actividad de los rodillos (autocontenida, sin librerías externas).

Una sola serie (actividad por captura), así que no lleva leyenda: el título la nombra. Los
umbrales de inicio y de reposo van como líneas de referencia discontinuas y discretas, y el
inicio y el fin del giro detectados se marcan sobre la serie. Cada punto tiene su valor al pasar
el ratón (title), y los colores salen de los tokens del informe (modo claro y oscuro).
"""

from collections.abc import Sequence
from html import escape

_WIDTH, _HEIGHT = 640, 210
_LEFT, _RIGHT, _TOP, _BOTTOM = 46, 16, 14, 34


def _fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def motion_chart(
    scores: Sequence[float],
    start_threshold: float,
    still_threshold: float,
    start_index: int | None = None,
    end_index: int | None = None,
) -> str:
    if not scores:
        return ""
    top_value = max(*scores, start_threshold) * 1.15 or 1.0
    plot_w, plot_h = _WIDTH - _LEFT - _RIGHT, _HEIGHT - _TOP - _BOTTOM
    step = plot_w / max(len(scores) - 1, 1)

    def x(index: int) -> float:
        return _LEFT + index * step

    def y(value: float) -> float:
        return _TOP + plot_h * (1 - value / top_value)

    grid = "".join(
        f'<line class="gridline" x1="{_LEFT}" x2="{_WIDTH - _RIGHT}" '
        f'y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        f'<text class="axis" x="{_LEFT - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{_fmt(v)}</text>'
        for v in (0.0, top_value / 2, top_value)
    )
    thresholds = "".join(
        f'<line class="threshold" x1="{_LEFT}" x2="{_WIDTH - _RIGHT}" '
        f'y1="{y(value):.1f}" y2="{y(value):.1f}"/>'
        f'<text class="axis" x="{_WIDTH - _RIGHT}" y="{y(value) - 4:.1f}" text-anchor="end">'
        f"{escape(label)} ({_fmt(value)})</text>"
        for value, label in ((start_threshold, "umbral de giro"), (still_threshold, "reposo"))
    )
    points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(scores))
    dots = "".join(
        f'<circle class="dot" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4">'
        f"<title>Captura {i + 1}: actividad {_fmt(v)}</title></circle>"
        for i, v in enumerate(scores)
    )

    def mark(index: int, label: str) -> str:
        # Cerca del borde derecho, el rótulo va a la izquierda de la línea para no salirse.
        near_edge = x(index) > _WIDTH - _RIGHT - 60
        anchor, dx = ("end", -4) if near_edge else ("start", 4)
        return (
            f'<line class="mark" x1="{x(index):.1f}" x2="{x(index):.1f}" '
            f'y1="{_TOP}" y2="{_TOP + plot_h}"/>'
            f'<text class="axis" x="{x(index) + dx:.1f}" y="{_TOP + 12}" '
            f'text-anchor="{anchor}">{escape(label)}</text>'
        )

    marks = "".join(
        mark(i, label)
        for i, label in ((start_index, "inicio"), (end_index, "fin"))
        if i is not None and 0 <= i < len(scores)
    )
    return (
        f'<svg class="chart" viewBox="0 0 {_WIDTH} {_HEIGHT}" role="img" '
        f'aria-label="Actividad de los rodillos en {len(scores)} capturas">'
        f"{grid}{thresholds}{marks}"
        f'<polyline class="line" points="{points}"/>{dots}'
        f'<text class="axis" x="{_LEFT + plot_w / 2:.1f}" y="{_HEIGHT - 8}" '
        f'text-anchor="middle">capturas tras pulsar girar →</text></svg>'
    )
