"""§6 TEST-PLAN — `oscillation_time_pct` (вікно 2 с = 20 семплів, поріг 3 зміни знаку)."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT, sine
from parser.metrics import oscillation_time_pct


def test_empty_series_has_zero_oscillation_share() -> None:
    # Arrange
    values = np.empty(0)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0


def test_series_shorter_than_window_has_zero_oscillation_share() -> None:
    # Arrange
    values = sine(2.0, duration_s=1.0, amplitude=1.0)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0


def test_series_inside_deadband_has_zero_oscillation_share() -> None:
    # Arrange
    values = np.full(300, 0.005)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0


def test_constant_deflection_has_zero_oscillation_share() -> None:
    # Arrange
    values = np.full(300, 0.5)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0


def test_slow_sine_below_window_resolution_has_zero_oscillation_share() -> None:
    # Arrange
    values = sine(0.25, duration_s=30.0, amplitude=1.0)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0


@pytest.mark.parametrize("frequency_hz", [1.0, 2.0, 3.0])
def test_fast_sine_marks_entire_series_as_oscillating(frequency_hz: float) -> None:
    # Arrange
    values = sine(frequency_hz, duration_s=30.0, amplitude=1.0)

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == pytest.approx(1.0)


def test_window_with_exactly_three_sign_changes_counts_as_oscillating() -> None:
    # Arrange
    values = np.concatenate(
        [np.full(5, 0.5), np.full(5, -0.5), np.full(5, 0.5), np.full(5, -0.5)]
    )

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == pytest.approx(1.0)


def test_window_with_only_one_sign_change_does_not_count_as_oscillating() -> None:
    # Arrange
    values = np.concatenate([np.full(10, 0.5), np.full(10, -0.5)])

    # Act
    result = oscillation_time_pct(values, dt=DT)

    # Assert
    assert result == 0.0
