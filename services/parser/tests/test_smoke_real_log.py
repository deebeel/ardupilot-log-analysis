"""§11 TEST-PLAN — smoke на реальному логу `assets/flight-01_2026-09-11.bin`."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from parser.models import MAX_SERIES_POINTS, FlightResult, write_json_atomic

EXPECTED_TOP_LEVEL_KEYS: set[str] = {
    "flight_id",
    "duration_s",
    "phases",
    "metrics",
    "default_thresholds",
    "series",
    "amplitude_histogram",
}

SERIES_CHANNELS: tuple[str, ...] = ("t", "roll", "pitch", "att_roll", "att_pitch")


def test_real_log_parses_into_a_result(real_result: FlightResult) -> None:
    # Arrange / парсинг виконано фікстурою

    # Act
    flight_id = real_result.flight_id

    # Assert
    assert flight_id == "flight-01_2026-09-11"


def test_real_result_matches_the_json_contract(real_result: FlightResult) -> None:
    # Arrange
    payload = real_result.to_dict()

    # Act
    keys = set(payload)

    # Assert
    assert EXPECTED_TOP_LEVEL_KEYS.issubset(keys)


def test_real_result_is_json_serializable_without_nan(real_result: FlightResult, tmp_path: Path) -> None:
    # Arrange
    destination = tmp_path / "flight-01.json"

    # Act
    write_json_atomic(real_result.to_dict(), destination)

    # Assert
    assert json.loads(destination.read_text())["flight_id"] == "flight-01_2026-09-11"


def test_real_log_duration_is_within_a_plausible_range(real_result: FlightResult) -> None:
    # Arrange
    duration = real_result.duration_s

    # Act
    plausible = 100.0 < duration < 10_000.0

    # Assert
    assert plausible, duration


def test_real_log_has_at_least_one_manual_phase(real_result: FlightResult) -> None:
    # Arrange
    phases = real_result.phases

    # Act
    manual_count = sum(phase.manual for phase in phases)

    # Assert
    assert manual_count > 0


def test_analyzed_duration_does_not_exceed_total_duration(real_result: FlightResult) -> None:
    # Arrange
    metrics_window = real_result.analyzed_duration_s

    # Act
    within = 0.0 < metrics_window <= real_result.duration_s

    # Assert
    assert within, (metrics_window, real_result.duration_s)


@pytest.mark.parametrize("axis", ["roll", "pitch", "yaw"])
def test_corrections_per_min_is_finite_and_plausible(real_result: FlightResult, axis: str) -> None:
    # Arrange
    value = real_result.metrics.corrections_per_min[axis]

    # Act
    plausible = math.isfinite(value) and 0.0 <= value <= 600.0

    # Assert
    assert plausible, value


@pytest.mark.parametrize("axis", ["roll", "pitch", "yaw"])
def test_mean_amplitude_is_within_normalized_range(real_result: FlightResult, axis: str) -> None:
    # Arrange
    value = real_result.metrics.mean_amplitude[axis]

    # Act
    within = math.isfinite(value) and 0.0 <= value <= 1.0

    # Assert
    assert within, value


@pytest.mark.parametrize("axis", ["roll", "pitch", "yaw"])
def test_oscillation_share_is_a_fraction(real_result: FlightResult, axis: str) -> None:
    # Arrange
    value = real_result.metrics.oscillation_time_pct[axis]

    # Act
    within = 0.0 <= value <= 1.0

    # Assert
    assert within, value


@pytest.mark.parametrize("axis", ["roll", "pitch", "yaw"])
def test_mean_jerk_is_finite_and_non_negative(real_result: FlightResult, axis: str) -> None:
    # Arrange
    value = real_result.metrics.mean_jerk[axis]

    # Act
    plausible = math.isfinite(value) and value >= 0.0

    # Assert
    assert plausible, value


@pytest.mark.parametrize("channel", SERIES_CHANNELS)
def test_series_channel_is_downsampled_within_the_point_limit(real_result: FlightResult, channel: str) -> None:
    # Arrange
    values = real_result.series[channel]

    # Act
    length = len(values)

    # Assert
    assert 0 < length <= MAX_SERIES_POINTS


def test_all_series_channels_share_the_same_length(real_result: FlightResult) -> None:
    # Arrange
    lengths = {len(real_result.series[channel]) for channel in SERIES_CHANNELS}

    # Act
    unique = len(lengths)

    # Assert
    assert unique == 1


def test_default_thresholds_are_embedded_for_the_client(real_result: FlightResult) -> None:
    # Arrange
    thresholds = real_result.default_thresholds

    # Act
    keys = set(thresholds)

    # Assert
    assert "mean_jerk" in keys


@pytest.mark.parametrize("axis", ["roll", "pitch", "yaw"])
def test_amplitude_histogram_edges_exceed_counts_by_one(real_result: FlightResult, axis: str) -> None:
    # Arrange
    histogram = real_result.amplitude_histogram[axis]

    # Act
    difference = len(histogram["bins"]) - len(histogram["counts"])

    # Assert
    assert difference == 1


def test_amplitude_histogram_has_all_three_axes(real_result: FlightResult) -> None:
    # Arrange / Act
    axes = set(real_result.amplitude_histogram.keys())

    # Assert
    assert axes == {"roll", "pitch", "yaw"}
