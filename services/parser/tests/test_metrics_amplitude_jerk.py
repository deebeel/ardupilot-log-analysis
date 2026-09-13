"""§4-§5 TEST-PLAN — `mean_amplitude` і `mean_jerk`."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT, FloatArray, ramp
from parser.metrics import DEADBAND, mean_amplitude, mean_jerk


def test_empty_series_has_zero_mean_amplitude() -> None:
    # Arrange
    values = np.empty(0)

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == 0.0


def test_series_inside_deadband_has_zero_mean_amplitude() -> None:
    # Arrange
    values = np.full(100, 0.01)

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == 0.0


def test_series_exactly_at_deadband_boundary_has_zero_mean_amplitude() -> None:
    # Arrange
    values = np.full(100, DEADBAND)

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == 0.0


@pytest.mark.parametrize("constant", [0.5, -0.5, 1.0])
def test_constant_deflection_amplitude_equals_its_absolute_value(constant: float) -> None:
    # Arrange
    values = np.full(100, constant)

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == pytest.approx(abs(constant))


def test_symmetric_deflections_average_by_absolute_value() -> None:
    # Arrange
    values = np.array([0.5, -0.5, 0.5, -0.5])

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == pytest.approx(0.5)


def test_neutral_samples_do_not_dilute_mean_amplitude() -> None:
    # Arrange
    values = np.concatenate([np.zeros(50), np.full(50, 0.4)])

    # Act
    result = mean_amplitude(values)

    # Assert
    assert result == pytest.approx(0.4)


@pytest.mark.parametrize("values", [np.empty(0), np.array([0.5])])
def test_series_shorter_than_two_samples_has_zero_jerk(values: FloatArray) -> None:
    # Arrange / параметризовано вище

    # Act
    result = mean_jerk(values, dt=DT)

    # Assert
    assert result == 0.0


def test_constant_series_has_zero_jerk() -> None:
    # Arrange
    values = np.full(100, 0.5)

    # Act
    result = mean_jerk(values, dt=DT)

    # Assert
    assert result == pytest.approx(0.0)


@pytest.mark.parametrize("slope_per_sample", [0.01, 0.05, -0.02])
def test_linear_ramp_jerk_equals_slope_per_second(slope_per_sample: float) -> None:
    # Arrange
    values = ramp(slope_per_sample, count=100)

    # Act
    result = mean_jerk(values, dt=DT)

    # Assert
    assert result == pytest.approx(abs(slope_per_sample) / DT)


def test_step_jerk_matches_three_sample_smoothing_result() -> None:
    # Arrange
    values = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])

    # Act
    result = mean_jerk(values, dt=0.1)

    # Assert
    assert result == pytest.approx(10.0 / 3.0)


def test_two_sample_series_falls_back_to_raw_difference() -> None:
    # Arrange
    values = np.array([0.0, 0.3])

    # Act
    result = mean_jerk(values, dt=0.1)

    # Assert
    assert result == pytest.approx(3.0)


def test_alternating_series_uses_absolute_differences_not_signed_sum() -> None:
    # Arrange
    values = np.array([0.0, 0.6, 0.0, 0.6, 0.0, 0.6])

    # Act
    result = mean_jerk(values, dt=DT)

    # Assert
    assert result > 0.0
