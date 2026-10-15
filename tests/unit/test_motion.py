import numpy as np
import pytest

from betsson_validator.perception.motion import (
    MotionThresholds,
    adaptive_thresholds,
    detect_spin_lifecycle,
    motion_score,
)


def blank(value: int = 0) -> np.ndarray:
    return np.full((100, 100, 3), value, dtype=np.uint8)


def test_identical_frames_have_no_motion() -> None:
    assert motion_score(blank(), blank()) == 0.0


def test_full_change_is_full_motion() -> None:
    assert motion_score(blank(0), blank(255)) == 1.0


def test_small_noise_is_ignored() -> None:
    assert motion_score(blank(100), blank(110)) == 0.0


def test_partial_change_is_proportional() -> None:
    changed = blank()
    changed[:50, :, :] = 255
    assert motion_score(blank(), changed) == pytest.approx(0.5)


def test_grayscale_frames_are_supported() -> None:
    assert motion_score(np.zeros((10, 10), np.uint8), np.full((10, 10), 255, np.uint8)) == 1.0


def test_different_sizes_are_rejected() -> None:
    with pytest.raises(ValueError, match="tamaño"):
        motion_score(blank(), np.zeros((50, 50, 3), np.uint8))


def test_full_spin_is_detected() -> None:
    scores = [0.0, 0.0, 0.3, 0.4, 0.35, 0.2, 0.0, 0.0, 0.0, 0.0]
    lifecycle = detect_spin_lifecycle(scores)
    assert lifecycle.started
    assert lifecycle.completed
    assert lifecycle.start_index == 2
    assert lifecycle.end_index == 9


def test_no_reaction_means_no_spin() -> None:
    lifecycle = detect_spin_lifecycle([0.0] * 10)
    assert not lifecycle.started
    assert not lifecycle.completed


def test_single_flicker_is_not_a_spin() -> None:
    lifecycle = detect_spin_lifecycle([0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert not lifecycle.started
    assert not lifecycle.completed


def test_spin_still_running_is_started_but_not_completed() -> None:
    lifecycle = detect_spin_lifecycle([0.0, 0.3, 0.3, 0.3, 0.3])
    assert lifecycle.started
    assert not lifecycle.completed


def test_thresholds_are_configurable() -> None:
    thresholds = MotionThresholds(start=0.5, still=0.01, still_samples=1, min_active_samples=1)
    assert not detect_spin_lifecycle([0.3, 0.0], thresholds).started
    assert detect_spin_lifecycle([0.6, 0.0], thresholds).completed


# Actividad visual medida en la zona de rodillos durante una tirada real de Sweet Bonanza 2500
# (15/10, una captura cada ~250 ms): giro con cascada y después reposo.
REAL_SPIN_SCORES = [
    0.40,
    0.19,
    0.30,
    0.15,
    0.03,
    0.05,
    0.20,
    0.29,
    0.15,
    0.05,
    0.09,
    0.10,
    0.05,
    0.22,
    0.10,
    0.21,
    0.12,
    0.11,
    0.03,
    *([0.0] * 20),
]


def test_real_spin_is_detected_start_to_end() -> None:
    lifecycle = detect_spin_lifecycle(REAL_SPIN_SCORES)
    assert lifecycle.started
    assert lifecycle.completed
    assert lifecycle.end_index == 21  # reposo al bajar del 10 % del máximo del giro


def test_static_game_keeps_default_thresholds() -> None:

    assert adaptive_thresholds([0.0, 0.0, 0.002]) == MotionThresholds()


def test_animated_background_is_not_mistaken_for_a_spin_that_never_ends() -> None:

    idle = [0.03, 0.04, 0.035]  # burbujas y personajes animados en reposo
    spin = [0.35, 0.30, 0.25, 0.20, *([0.035] * 6)]
    assert not detect_spin_lifecycle(spin).completed  # con umbrales fijos, nunca "reposa"
    lifecycle = detect_spin_lifecycle(spin, adaptive_thresholds(idle))
    assert lifecycle.started and lifecycle.completed


def test_background_animation_alone_is_not_a_spin() -> None:

    idle = [0.03, 0.04, 0.035]
    assert not detect_spin_lifecycle([0.04] * 20, adaptive_thresholds(idle)).started


# Tirada real de Big Bass Halloween Splash 1000 (15/10): tras el giro, los peces premiados
# siguen brillando (~0,012 de actividad residual, por encima del umbral fijo de reposo).
BIG_BASS_SPIN_SCORES = [
    0.0006,
    0.7368,
    0.4905,
    0.4717,
    0.5814,
    0.6499,
    0.6149,
    0.5973,
    0.4388,
    0.446,
    0.2838,
    0.2801,
    0.2585,
    0.275,
    0.2772,
    0.2912,
    0.2657,
    0.2687,
    0.2816,
    0.2738,
    0.2785,
    0.2715,
    0.2322,
    0.2112,
    0.1489,
    0.15,
    0.1273,
    0.1459,
    0.144,
    0.1435,
    0.1537,
    0.1563,
    0.143,
    0.091,
    0.1102,
    0.1233,
    0.1991,
    0.1712,
    0.1149,
    0.0483,
    0.0138,
    0.0128,
    0.0127,
    0.0134,
    *([0.0125] * 40),
]


def test_real_spin_with_residual_glow_completes() -> None:
    lifecycle = detect_spin_lifecycle(BIG_BASS_SPIN_SCORES)
    assert lifecycle.started
    assert lifecycle.completed
    assert 39 <= (lifecycle.end_index or 0) <= 44


def test_isolated_flashes_separated_by_rests_are_not_a_spin() -> None:
    """Auditoría R02 (MOV-003): destellos sueltos no se acumulan como un giro."""
    rest = [0.0] * 5
    flashes = [0.3, *rest, 0.3, *rest, 0.3, *rest]
    lifecycle = detect_spin_lifecycle(flashes)
    assert not lifecycle.completed
    assert not lifecycle.started
