"""§7 TEST-PLAN — `attitude_events` і `reaction_latency_ms`.

Подія конструюється як одиничний різкий сплеск attitude: baseline (5 с = 50 семплів)
розмазує сплеск на 100/50 = 2°, тож рівно один семпл перевищує поріг 10°.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT, FloatArray
from parser.metrics import attitude_events, reaction_latency_ms

SPIKE_DEG: float = 100.0


def attitude_with_spikes(
    length: int, spike_indices: list[int], width: int = 1
) -> FloatArray:
    """Нульовий attitude з різкими сплесками заданої ширини."""
    series = np.zeros(length)
    for index in spike_indices:
        series[index : index + width] = SPIKE_DEG
    return series


def stick_with_moves(length: int, move_indices: list[int]) -> FloatArray:
    """Нейтральний стік із рухом поза deadband у заданих семплах."""
    series = np.zeros(length)
    for index in move_indices:
        series[index:] = 0.5
    return series


def test_empty_series_yields_no_latency() -> None:
    # Arrange
    attitude = np.empty(0)

    # Act
    result = reaction_latency_ms(attitude, np.empty(0), dt=DT)

    # Assert
    assert result is None


def test_attitude_never_exceeding_threshold_yields_no_latency() -> None:
    # Arrange
    attitude = np.full(200, 1.0)

    # Act
    result = reaction_latency_ms(attitude, stick_with_moves(200, [50]), dt=DT)

    # Assert
    assert result is None


def test_attitude_event_without_any_operator_input_yields_no_latency() -> None:
    # Arrange
    attitude = attitude_with_spikes(200, [100])

    # Act
    result = reaction_latency_ms(attitude, np.zeros(200), dt=DT)

    # Assert
    assert result is None


def test_single_spike_produces_exactly_one_event() -> None:
    # Arrange
    attitude = attitude_with_spikes(200, [100])

    # Act
    events = attitude_events(attitude, dt=DT)

    # Assert
    assert events.tolist() == [100]


def test_sustained_event_is_not_counted_twice() -> None:
    # Arrange
    attitude = attitude_with_spikes(200, [100], width=2)

    # Act
    events = attitude_events(attitude, dt=DT)

    # Assert
    assert events.tolist() == [100]


@pytest.mark.parametrize(
    ("reaction_offset", "expected_ms"),
    [(0, 0.0), (1, 100.0), (5, 500.0), (20, 2000.0)],
)
def test_single_event_latency_equals_offset_to_first_stick_move(
    reaction_offset: int, expected_ms: float
) -> None:
    # Arrange
    attitude = attitude_with_spikes(400, [100])
    stick = stick_with_moves(400, [100 + reaction_offset])

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result == pytest.approx(expected_ms)


def test_reaction_after_waiting_window_is_ignored() -> None:
    # Arrange
    attitude = attitude_with_spikes(400, [100])
    stick = stick_with_moves(400, [136])

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result is None


def test_two_events_yield_median_of_their_latencies() -> None:
    # Arrange
    attitude = attitude_with_spikes(500, [100, 300])
    stick = np.zeros(500)
    stick[102:110] = 0.5
    stick[306:314] = 0.5

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result == pytest.approx(400.0)


def test_three_events_yield_middle_latency_as_median() -> None:
    # Arrange
    attitude = attitude_with_spikes(700, [100, 300, 500])
    stick = np.zeros(700)
    stick[102:110] = 0.5
    stick[304:312] = 0.5
    stick[510:518] = 0.5

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result == pytest.approx(400.0)
