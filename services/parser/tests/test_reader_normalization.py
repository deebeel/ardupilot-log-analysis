"""§1 і §8 TEST-PLAN — нормалізація RC, калібрування з PARM, фази та ручна маска."""

from __future__ import annotations

import numpy as np
import pytest

from parser.reader import (
    DEFAULT_RC_MAX,
    DEFAULT_RC_MIN,
    DEFAULT_RC_TRIM,
    RcCalibration,
    build_phases,
    manual_mask_from_phases,
    mode_name,
    normalize_channel,
    rc_calibrations,
    resample,
)

SYMMETRIC: RcCalibration = RcCalibration(1000.0, 1500.0, 2000.0)
ASYMMETRIC: RcCalibration = RcCalibration(1100.0, 1500.0, 2000.0)


@pytest.mark.parametrize(
    ("pwm", "expected"),
    [(1500.0, 0.0), (2000.0, 1.0), (1000.0, -1.0), (1750.0, 0.5), (1250.0, -0.5)],
)
def test_symmetric_calibration_maps_pwm_to_normalized_range(pwm: float, expected: float) -> None:
    # Arrange
    calibration = SYMMETRIC

    # Act
    result = normalize_channel(pwm, calibration)

    # Assert
    assert float(result) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("pwm", "expected"),
    [(1300.0, -0.5), (1750.0, 0.5), (1100.0, -1.0), (2000.0, 1.0)],
)
def test_asymmetric_calibration_uses_separate_half_ranges(pwm: float, expected: float) -> None:
    # Arrange
    calibration = ASYMMETRIC

    # Act
    result = normalize_channel(pwm, calibration)

    # Assert
    assert float(result) == pytest.approx(expected)


@pytest.mark.parametrize(("pwm", "expected"), [(2500.0, 1.0), (500.0, -1.0)])
def test_pwm_outside_calibrated_range_is_clipped(pwm: float, expected: float) -> None:
    # Arrange
    calibration = SYMMETRIC

    # Act
    result = normalize_channel(pwm, calibration)

    # Assert
    assert float(result) == pytest.approx(expected)


def test_degenerate_calibration_yields_zero_without_dividing_by_zero() -> None:
    # Arrange
    calibration = RcCalibration(1500.0, 1500.0, 1500.0)

    # Act
    result = normalize_channel(np.array([1400.0, 1500.0, 1600.0]), calibration)

    # Assert
    assert result.tolist() == [0.0, 0.0, 0.0]


def test_missing_rc_parameters_fall_back_to_default_calibration() -> None:
    # Arrange
    params: dict[str, float] = {}

    # Act
    result = rc_calibrations(params)

    # Assert
    assert result["roll"] == RcCalibration(DEFAULT_RC_MIN, DEFAULT_RC_TRIM, DEFAULT_RC_MAX)


def test_partial_rc_parameters_keep_defaults_for_absent_fields() -> None:
    # Arrange
    params = {"RC1_TRIM": 1480.0}

    # Act
    result = rc_calibrations(params)

    # Assert
    assert result["roll"] == RcCalibration(DEFAULT_RC_MIN, 1480.0, DEFAULT_RC_MAX)


@pytest.mark.parametrize(
    ("number", "expected"), [(0, "MANUAL"), (5, "FBWA"), (6, "FBWB"), (10, "AUTO"), (99, "MODE_99")]
)
def test_mode_number_maps_to_expected_name(number: int, expected: str) -> None:
    # Arrange / параметризовано вище

    # Act
    result = mode_name(number)

    # Assert
    assert result == expected


def test_last_phase_is_closed_by_log_end_timestamp() -> None:
    # Arrange
    changes = [(10.0, "FBWA"), (20.0, "AUTO")]

    # Act
    phases = build_phases(changes, start_s=10.0, end_s=35.0)

    # Assert
    assert phases[-1]["end_s"] == pytest.approx(25.0)


def test_automatic_modes_are_marked_as_not_manual() -> None:
    # Arrange
    changes = [(0.0, "FBWA"), (10.0, "AUTO"), (20.0, "RTL")]

    # Act
    phases = build_phases(changes, start_s=0.0, end_s=30.0)

    # Assert
    assert [phase["manual"] for phase in phases] == [True, False, False]


def test_log_without_mode_records_produces_no_phases() -> None:
    # Arrange
    changes: list[tuple[float, str]] = []

    # Act
    phases = build_phases(changes, start_s=0.0, end_s=30.0)

    # Assert
    assert phases == []


def test_manual_mask_selects_only_samples_inside_manual_phases() -> None:
    # Arrange
    grid = np.arange(0.0, 30.0, 1.0)
    phases = build_phases([(0.0, "FBWA"), (10.0, "AUTO")], start_s=0.0, end_s=30.0)

    # Act
    mask = manual_mask_from_phases(grid, phases)

    # Assert
    assert int(np.count_nonzero(mask)) == 10


def test_log_without_manual_modes_yields_empty_analysis_mask() -> None:
    # Arrange
    grid = np.arange(0.0, 30.0, 1.0)
    phases = build_phases([(0.0, "AUTO"), (10.0, "RTL")], start_s=0.0, end_s=30.0)

    # Act
    mask = manual_mask_from_phases(grid, phases)

    # Assert
    assert int(np.count_nonzero(mask)) == 0


def test_resampling_interpolates_onto_the_common_grid() -> None:
    # Arrange
    times = np.array([0.0, 2.0])
    values = np.array([0.0, 20.0])

    # Act
    result = resample(times, values, np.array([0.0, 1.0, 2.0]))

    # Assert
    assert result.tolist() == [0.0, 10.0, 20.0]


def test_resampling_empty_source_yields_zero_filled_grid() -> None:
    # Arrange
    grid = np.array([0.0, 1.0, 2.0])

    # Act
    result = resample(np.empty(0), np.empty(0), grid)

    # Assert
    assert result.tolist() == [0.0, 0.0, 0.0]
