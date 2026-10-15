import numpy as np
import pytest

from betsson_validator.perception.motion import (
    MotionThresholds,
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
    assert lifecycle.end_index == 22
