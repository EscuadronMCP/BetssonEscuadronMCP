"""Sonda de accesibilidad: mide sin cambiar veredictos y nunca rompe la prueba."""

from typing import Any, cast

from playwright.sync_api import Error as PlaywrightError

from betsson_validator.game.accessibility import MAX_NAMES, probe, summarize_aria


def test_an_empty_canvas_game_is_measured_as_empty() -> None:
    result = summarize_aria("antes_de_girar", "")
    assert result.status == "vacío"
    assert result.nodes == 0


def test_roles_and_names_are_counted() -> None:
    snapshot = '- button "Girar"\n- button "Apuesta +"\n- text: Saldo 193,74 €\n- img'
    result = summarize_aria("despues_de_girar", snapshot)
    assert result.status == "con datos"
    assert result.roles == {"button": 2, "text": 1, "img": 1}
    assert result.names == ("Girar", "Apuesta +")


def test_names_are_bounded() -> None:
    snapshot = "\n".join(f'- button "{"x" * 500}{n}"' for n in range(100))
    result = summarize_aria("antes_de_girar", snapshot)
    assert len(result.names) == MAX_NAMES
    assert all(len(name) <= 80 for name in result.names)


class _Frame:
    """Marco simulado: su árbol ARIA y sus iframes (con su tamaño en pantalla)."""

    def __init__(self, snapshot: str, children: list[tuple["_Frame", float]] | None = None) -> None:
        self.snapshot, self.children = snapshot, children or []
        self._selector = ""

    def locator(self, selector: str) -> "_Frame":
        self._selector = selector
        return self

    def count(self) -> int:
        return len(self.children) if self._selector == "iframe" else 1

    def nth(self, index: int) -> Any:
        _child, area = self.children[index]
        return type("Iframe", (), {"bounding_box": lambda _s, **_k: {"width": area, "height": 1}})()

    def frame_locator(self, _selector: str) -> Any:
        children = self.children
        return type("Frames", (), {"nth": lambda _s, i: children[i][0]})()

    def aria_snapshot(self, **_kwargs: object) -> str:
        return self.snapshot


def test_a_failing_probe_is_reported_not_raised() -> None:
    class Broken(_Frame):
        def aria_snapshot(self, **_kwargs: object) -> str:
            raise PlaywrightError("marco no disponible")

    result = probe(cast(Any, Broken("")), "antes_de_girar")
    assert result.status == "error"
    assert "Error" in result.detail


def test_the_probe_reaches_the_nested_game_next_to_other_controls() -> None:
    """«Ayuda» + iframe del juego: hay que llegar al juego."""
    game = _Frame('- button "Girar"')
    advert = _Frame('- link "Anuncio"')
    launcher = _Frame('- button "Ayuda"\n- iframe', children=[(advert, 10.0), (game, 900.0)])
    result = probe(cast(Any, launcher), "despues_de_girar", settled=False)
    assert result.roles == {"button": 1}
    assert result.names == ("Girar",)
    assert result.detail.startswith("marco de nivel 2")
    assert "sin estabilizar" in result.detail
