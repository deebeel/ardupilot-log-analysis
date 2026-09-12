"""§8.3 TEST-PLAN — агрегація метрик по ручних сегментах."""

from __future__ import annotations

import numpy as np
import pytest

from parser.reader import DT, FlightData
from parser.worker import compute_metrics, contiguous_segments, flight_id_from_path


def make_flight(manual_mask: np.ndarray, roll: np.ndarray | None = None) -> FlightData:
    """FlightData з керованою маскою — без читання реального логу."""
    size = manual_mask.size
    grid = np.arange(size, dtype=float) * DT
    roll_series = np.zeros(size) if roll is None else roll
    return FlightData(
        t=grid,
        sticks={"roll": roll_series, "pitch": np.zeros(size), "yaw": np.zeros(size)},
        att_roll=np.zeros(size),
        att_pitch=np.zeros(size),
        manual_mask=manual_mask,
        phases=[],
    )


@pytest.mark.parametrize(
    ("mask", "expected"),
    [
        ([False, False], []),
        ([True, True], [(0, 2)]),
        ([True, False, True], [(0, 1), (2, 3)]),
        ([False, True, True, False, True], [(1, 3), (4, 5)]),
    ],
)
def test_contiguous_segments_splits_the_mask_into_blocks(mask, expected):
    # Arrange
    array = np.array(mask, dtype=bool)

    # Act
    result = contiguous_segments(array)

    # Assert
    assert result == expected


def test_empty_mask_produces_no_segments():
    # Arrange
    array = np.empty(0, dtype=bool)

    # Act
    result = contiguous_segments(array)

    # Assert
    assert result == []


def test_log_without_manual_modes_yields_zero_metrics():
    # Arrange
    flight = make_flight(np.zeros(600, dtype=bool), roll=np.full(600, 0.8))

    # Act
    result = compute_metrics(flight)

    # Assert
    assert result.corrections_per_min == {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}


def test_log_without_manual_modes_yields_null_reaction_latency():
    # Arrange
    flight = make_flight(np.zeros(600, dtype=bool), roll=np.full(600, 0.8))

    # Act
    result = compute_metrics(flight)

    # Assert
    assert result.reaction_latency_ms is None


def test_metrics_ignore_samples_outside_manual_phases():
    # Arrange
    mask = np.concatenate([np.ones(600, dtype=bool), np.zeros(600, dtype=bool)])
    roll = np.concatenate([np.zeros(600), np.full(600, 0.9)])
    flight = make_flight(mask, roll=roll)

    # Act
    result = compute_metrics(flight)

    # Assert
    assert result.mean_amplitude["roll"] == 0.0


def test_constant_deflection_over_one_manual_minute_gives_one_correction_per_min():
    # Arrange
    flight = make_flight(np.ones(600, dtype=bool), roll=np.full(600, 0.5))

    # Act
    result = compute_metrics(flight)

    # Assert
    assert result.corrections_per_min["roll"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/data/inbox/flight-01_2026-09-11.bin", "flight-01_2026-09-11"),
        ("flight 02.BIN", "flight_02"),
        ("/x/../weird@name.bin", "weird_name"),
    ],
)
def test_flight_id_is_derived_safely_from_the_file_name(path, expected):
    # Arrange / параметризовано вище

    # Act
    result = flight_id_from_path(path)

    # Assert
    assert result == expected
