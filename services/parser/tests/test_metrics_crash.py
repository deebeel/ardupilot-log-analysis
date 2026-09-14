"""`detect_crash_heuristic` — доповнює `STAT.Crash` (AUTO-only) для ручних режимів.

Хвіст логу (`CRASH_TAIL_WINDOW_S`) на низькій висоті (`CRASH_ALT_THRESHOLD_M`)
з екстремальним креном/тангажем (`CRASH_ATTITUDE_THRESHOLD_DEG`) -> удар, не
керована посадка.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT
from parser.metrics import (
    CRASH_ALT_THRESHOLD_M,
    CRASH_ATTITUDE_THRESHOLD_DEG,
    detect_crash_heuristic,
)


def _constant(value: float, count: int = 100) -> np.ndarray:
    return np.full(count, value, dtype=np.float64)


def test_high_altitude_tail_is_never_a_crash_regardless_of_attitude() -> None:
    # Arrange
    rel_alt = _constant(50.0)
    roll = _constant(80.0)
    pitch = _constant(80.0)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is False


def test_low_altitude_with_level_attitude_is_a_controlled_landing() -> None:
    # Arrange
    rel_alt = _constant(0.5)
    roll = _constant(2.0)
    pitch = _constant(-3.0)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "roll_deg, pitch_deg",
    [
        (CRASH_ATTITUDE_THRESHOLD_DEG + 1.0, 0.0),
        (0.0, CRASH_ATTITUDE_THRESHOLD_DEG + 1.0),
        (-(CRASH_ATTITUDE_THRESHOLD_DEG + 1.0), 0.0),
    ],
)
def test_low_altitude_with_extreme_roll_or_pitch_is_a_crash(roll_deg: float, pitch_deg: float) -> None:
    # Arrange
    rel_alt = _constant(0.5)
    roll = _constant(roll_deg)
    pitch = _constant(pitch_deg)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is True


def test_altitude_exactly_at_threshold_is_still_ground_level() -> None:
    # Arrange (межа включно, як і в outside_deadband/categorize по всьому проєкту)
    rel_alt = _constant(CRASH_ALT_THRESHOLD_M)
    roll = _constant(CRASH_ATTITUDE_THRESHOLD_DEG + 1.0)
    pitch = _constant(0.0)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is True


def test_empty_rel_alt_is_not_a_crash() -> None:
    # Arrange
    rel_alt = np.empty(0)
    roll = np.empty(0)
    pitch = np.empty(0)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is False


def test_non_positive_dt_is_not_a_crash() -> None:
    # Arrange
    rel_alt = _constant(0.0)
    roll = _constant(90.0)
    pitch = _constant(90.0)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, dt=0.0)

    # Assert
    assert result is False


def test_tail_window_larger_than_available_data_uses_whole_series() -> None:
    # Arrange (лише 5 семплів, вікно за замовчуванням — 3с/DT=30 семплів)
    rel_alt = _constant(0.5, count=5)
    roll = _constant(CRASH_ATTITUDE_THRESHOLD_DEG + 1.0, count=5)
    pitch = _constant(0.0, count=5)

    # Act
    result = detect_crash_heuristic(rel_alt, roll, pitch, DT)

    # Assert
    assert result is True
