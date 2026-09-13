"""§3 TEST-PLAN — `corrections_per_min`."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT, sine
from parser.metrics import DEADBAND, corrections_per_min


def test_empty_series_yields_zero_corrections() -> None:
    # Arrange
    values = np.empty(0)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == 0.0


def test_series_entirely_inside_deadband_yields_zero_corrections() -> None:
    # Arrange
    values = np.full(600, 0.01)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == 0.0


def test_series_exactly_at_deadband_boundary_is_treated_as_neutral() -> None:
    # Arrange
    values = np.full(600, DEADBAND)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == 0.0


def test_constant_deflection_without_return_counts_as_single_correction() -> None:
    # Arrange
    values = np.full(600, 0.5)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == pytest.approx(1.0)


def test_single_excursion_and_return_counts_as_single_correction() -> None:
    # Arrange
    values = np.concatenate([np.zeros(200), np.full(200, 0.5), np.zeros(200)])

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("frequency_hz", "expected"),
    # Вище ~1 Гц сітка 10 Гц уже не має семплів усередині deadband на переході через нуль
    # (5 семплів на період), тож метрика фізично недорахує виходи — це межа роздільності.
    [(0.2, 24.0), (0.5, 60.0), (1.0, 120.0)],
)
def test_ideal_sine_yields_two_deadband_exits_per_period(frequency_hz: float, expected: float) -> None:
    # Arrange
    values = sine(frequency_hz, duration_s=60.0, amplitude=1.0)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == pytest.approx(expected, rel=0.02)


def test_sine_smaller_than_deadband_yields_no_corrections() -> None:
    # Arrange
    values = sine(1.0, duration_s=60.0, amplitude=DEADBAND / 2.0)

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == 0.0


def test_zero_duration_yields_zero_instead_of_division_error() -> None:
    # Arrange
    values = np.full(10, 0.5)

    # Act
    result = corrections_per_min(values, duration_s=0.0)

    # Assert
    assert result == 0.0


def test_correction_counted_only_on_outward_crossing_not_on_every_sample() -> None:
    # Arrange
    values = np.concatenate([np.zeros(10), np.full(int(60 / DT) - 10, 0.5)])

    # Act
    result = corrections_per_min(values, duration_s=60.0)

    # Assert
    assert result == pytest.approx(1.0)
