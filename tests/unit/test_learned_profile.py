"""El perfil aprendido de verdad (profiles/) sobre capturas reales de sesiones distintas.

Exige que cada control se encuentre donde está y SOLO donde está: pulsar el control equivocado
(p. ej. '+' en lugar de '-', o 'girar' en lugar de 'continuar') costaría dinero real.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from betsson_validator.game.player import ScreenModel
from betsson_validator.perception.ocr import RapidOcrReader
from betsson_validator.profiles import GameProfile, load_profile

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pragmaticplay"
SPIN, BET_DOWN, BET_UP, CONTINUE = (697, 456), (625, 457), (762, 457), (714, 334)
TOLERANCE_PX = 15


def load(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None
    return np.asarray(image, dtype=np.uint8)


@pytest.fixture(scope="module")
def model() -> ScreenModel:
    profile = load_profile("pragmaticplay", "sweet-bonanza-2500")
    assert isinstance(profile, GameProfile)
    return ScreenModel(profile, RapidOcrReader(), "EUR", None)


def located(model: ScreenModel, control: str, image: np.ndarray) -> tuple[int, int] | None:
    point = model.locate(control, image)
    if point is None:
        return None
    height, width = image.shape[:2]
    return round(point[0] * width), round(point[1] * height)


def near(found: tuple[int, int] | None, expected: tuple[int, int]) -> bool:
    return found is not None and all(
        abs(a - b) <= TOLERANCE_PX for a, b in zip(found, expected, strict=True)
    )


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("sweet_bonanza_ready.png", {"spin": SPIN, "bet_down": BET_DOWN, "bet_up": BET_UP}),
        ("sweet_bonanza_intro.png", {"continue": CONTINUE}),
        ("sweet_bonanza_after_spin.png", {"spin": SPIN, "bet_up": BET_UP}),
        ("sweet_bonanza_insufficient_funds.png", {"spin": SPIN, "bet_up": BET_UP}),
    ],
)
def test_each_control_is_found_only_where_it_is(
    model: ScreenModel, fixture: str, expected: dict[str, tuple[int, int]]
) -> None:
    image = load(fixture)
    for control in ("spin", "bet_down", "bet_up", "continue"):
        found = located(model, control, image)
        if control in expected:
            assert near(found, expected[control]), f"{control} en {fixture}: {found}"
        else:
            assert found is None, f"{control} no debería localizarse en {fixture}: {found}"


def test_profile_labels_read_the_real_hud(model: ScreenModel) -> None:
    hud, _ = model.read(load("sweet_bonanza_ready.png"))
    assert hud.credit is not None and hud.bet is not None


def test_two_identical_controls_are_ambiguous_and_never_clicked(model: ScreenModel) -> None:
    """Auditoría: con dos plantillas idénticas el empate se resolvía a favor del control pedido."""
    image = load("sweet_bonanza_ready.png")
    spin = model.profile.template("spin")
    assert spin is not None
    clone = ScreenModel(
        GameProfile(
            provider="pragmaticplay",
            game="clon",
            credit_label=model.profile.credit_label,
            bet_label=model.profile.bet_label,
            win_label=model.profile.win_label,
            templates={"spin": spin, "bet_up": spin.copy()},
        ),
        RapidOcrReader(),
        "EUR",
        None,
    )
    assert clone.locate("spin", image) is None
    assert clone.locate("bet_up", image) is None


def test_real_profiles_know_their_minimum_bet() -> None:
    from decimal import Decimal  # noqa: PLC0415

    sweet = load_profile("pragmaticplay", "sweet-bonanza-2500")
    bass = load_profile("pragmaticplay", "big-bass-halloween-splash-1000")
    assert sweet is not None and sweet.min_bet == Decimal("0.20")
    assert bass is not None and bass.min_bet == Decimal("0.10")


def test_saving_writes_everything_or_keeps_the_previous_profile(tmp_path: Path) -> None:
    """Auditoría R03-01: el perfil se publica entero o no se publica."""
    profile = load_profile("pragmaticplay", "sweet-bonanza-2500")
    assert profile is not None
    profile.save(tmp_path)
    reloaded = load_profile("pragmaticplay", "sweet-bonanza-2500", tmp_path)
    assert reloaded is not None
    assert reloaded.credit_label == profile.credit_label
    assert set(reloaded.templates) == set(profile.templates)
    assert reloaded.min_bet == profile.min_bet

    broken = load_profile("pragmaticplay", "sweet-bonanza-2500")
    assert broken is not None
    broken.credit_label = "OTRA"
    broken.templates["spin"] = np.zeros((0, 0, 3), dtype=np.uint8)  # imagen imposible de escribir
    with pytest.raises(Exception):  # noqa: B017
        broken.save(tmp_path)
    kept = load_profile("pragmaticplay", "sweet-bonanza-2500", tmp_path)
    assert kept is not None and kept.credit_label == profile.credit_label


def test_bet_controls_far_from_spin_are_never_pressed() -> None:
    """15/10 (real): un falso «-» de Big Bass en (0,68; 0,32) abrió la tirada automática."""
    from betsson_validator.game.player import near_spin  # noqa: PLC0415

    spin = (0.776, 0.901)
    assert near_spin((0.698, 0.907), spin)  # «-» real de Sweet Bonanza
    assert near_spin((0.700, 0.930), spin)  # «-» real de Big Bass
    assert not near_spin((0.682, 0.321), spin)  # el falso «-» dentro del panel
    assert not near_spin((0.698, 0.907), None)  # sin girar localizado, no se pulsa
