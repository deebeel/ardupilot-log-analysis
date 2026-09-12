"""§9 TEST-PLAN — контракт вихідного JSON, downsample, гістограма, атомарний запис."""

from __future__ import annotations

import json

import numpy as np
import pytest

from parser.metrics import amplitude_histogram, outside_deadband
from parser.models import (
    FORBIDDEN_KEYS,
    MAX_SERIES_POINTS,
    FlightResult,
    Metrics,
    downsample,
    load_thresholds,
    write_error,
    write_json_atomic,
)

EXPECTED_TOP_LEVEL_KEYS = {
    "flight_id",
    "duration_s",
    "phases",
    "metrics",
    "default_thresholds",
    "series",
    "amplitude_histogram",
}

AXES = {"roll": 1.0, "pitch": 2.0, "yaw": 3.0}


def make_result(latency: float | None = 420.0, points: int = 10) -> FlightResult:
    """Мінімальний валідний результат для перевірок контракту."""
    return FlightResult(
        flight_id="flight-99_2026-01-01",
        duration_s=123.4,
        phases=[],
        metrics=Metrics(dict(AXES), dict(AXES), dict(AXES), dict(AXES), latency),
        default_thresholds={"mean_jerk": {"good_max": 0.6, "warn_max": 1.2}},
        series={key: [0.0] * points for key in ("t", "roll", "pitch", "att_roll", "att_pitch")},
        amplitude_histogram={"bin_edges": [0.0, 1.0], "counts": [5]},
    )


def test_result_exposes_all_contract_keys():
    # Arrange
    result = make_result()

    # Act
    payload = result.to_dict()

    # Assert
    assert EXPECTED_TOP_LEVEL_KEYS.issubset(payload.keys())


@pytest.mark.parametrize("forbidden", FORBIDDEN_KEYS)
def test_server_result_never_contains_a_precomputed_verdict(forbidden):
    # Arrange
    result = make_result()

    # Act
    payload = result.to_dict()

    # Assert
    assert forbidden not in payload


def test_long_series_is_downsampled_to_the_point_limit():
    # Arrange
    values = np.arange(50_000, dtype=float)

    # Act
    result = downsample(values)

    # Assert
    assert len(result) == MAX_SERIES_POINTS


def test_short_series_is_not_upsampled():
    # Arrange
    values = np.arange(37, dtype=float)

    # Act
    result = downsample(values)

    # Assert
    assert len(result) == 37


def test_downsampling_preserves_first_and_last_samples():
    # Arrange
    values = np.arange(50_000, dtype=float)

    # Act
    result = downsample(values)

    # Assert
    assert (result[0], result[-1]) == (0.0, 49_999.0)


def test_null_latency_serializes_as_json_null():
    # Arrange
    result = make_result(latency=None)

    # Act
    payload = json.loads(json.dumps(result.to_dict(), allow_nan=False))

    # Assert
    assert payload["metrics"]["reaction_latency_ms"] is None


def test_histogram_edges_are_one_longer_than_counts():
    # Arrange
    values = np.linspace(-1.0, 1.0, 500)

    # Act
    edges, counts = amplitude_histogram(values)

    # Assert
    assert len(edges) == len(counts) + 1


def test_histogram_counts_only_samples_outside_deadband():
    # Arrange
    values = np.concatenate([np.zeros(100), np.full(60, 0.4)])

    # Act
    _, counts = amplitude_histogram(values)

    # Assert
    assert sum(counts) == int(np.count_nonzero(outside_deadband(values)))


def test_atomic_write_leaves_no_temporary_file_behind(tmp_path):
    # Arrange
    destination = tmp_path / "flight-99.json"

    # Act
    write_json_atomic(make_result().to_dict(), destination)

    # Assert
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_produces_readable_json(tmp_path):
    # Arrange
    destination = tmp_path / "flight-99.json"

    # Act
    write_json_atomic(make_result().to_dict(), destination)

    # Assert
    assert json.loads(destination.read_text())["flight_id"] == "flight-99_2026-01-01"


def test_error_result_carries_the_failure_message(tmp_path):
    # Arrange
    message = "DFReader blew up"

    # Act
    path = write_error("flight-99", message, tmp_path)

    # Assert
    assert json.loads(path.read_text())["error"] == message


def test_missing_thresholds_file_yields_empty_config(tmp_path):
    # Arrange
    missing = tmp_path / "absent.yaml"

    # Act
    result = load_thresholds(missing)

    # Assert
    assert result == {}


def test_default_thresholds_file_defines_all_five_metrics():
    # Arrange
    from conftest import THRESHOLDS

    # Act
    config = load_thresholds(THRESHOLDS)

    # Assert
    assert set(config) == {
        "corrections_per_min",
        "mean_amplitude",
        "mean_jerk",
        "oscillation_time_pct",
        "reaction_latency_ms",
    }
