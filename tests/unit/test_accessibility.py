"""Sonda de accesibilidad: mide sin cambiar veredictos y nunca rompe la prueba (auditoría AX)."""

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


def test_a_failing_probe_is_reported_not_raised() -> None:
    class BrokenFrame:
        def locator(self, _selector: str) -> "BrokenFrame":
            return self

        def aria_snapshot(self, **_kwargs: object) -> str:
            raise PlaywrightError("marco no disponible")

    result = probe(cast(Any, BrokenFrame()), "antes_de_girar")
    assert result.status == "error"
    assert result.detail == "Error"
