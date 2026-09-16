"""Тести циклу відправки — фейковий mavlink і керований годинник, без sleep і мережі.

Сценарії 22-26 з TEST-PLAN.md.
"""

from __future__ import annotations

from typing import Mapping

import pytest

from keyboard_adapter.axes import AxisState
from keyboard_adapter.loop import run_loop, send_manual_control
from helpers import FakeClock, FakeMav, ScriptedKeys

RATE = 2000.0


# 22, 23
@pytest.mark.parametrize("duration, expected", [(1.0, 20), (0.5, 10), (0.05, 1), (2.0, 40)])
def test_loop_sends_at_fixed_rate_for_duration(duration: float, expected: int) -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys(["d"])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=duration, state=AxisState(rate=RATE))

    # Assert
    assert len(mav.calls) == expected


# 22
def test_loop_advances_clock_by_exactly_the_duration() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0)

    # Assert
    assert clock.monotonic() == pytest.approx(1.0)


# 24
def test_loop_keeps_sending_when_no_key_is_pressed() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0)

    # Assert
    assert len(mav.calls) == 20


# 24
def test_loop_with_no_key_pressed_sends_only_neutral_packets() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0)

    # Assert
    assert set(mav.calls) == {(0, 0, 0, 0, 0, 0)}


# 22
def test_loop_polls_keyboard_once_per_packet() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys(["w"])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0)

    # Assert
    assert keys.calls == 20


# 25
def test_send_manual_control_maps_axes_to_mavlink_fields() -> None:
    # Arrange
    mav = FakeMav()
    values = {"pitch": 100.0, "roll": -200.0, "throttle": 300.4, "yaw": -400.9}

    # Act
    send_manual_control(mav, values, target=7)

    # Assert
    assert mav.calls == [(7, 100, -200, 300, -400, 0)]


# 26
def test_loop_ramps_throttle_into_packets_without_spring_return() -> None:
    # Arrange
    mav, clock = FakeMav(), FakeClock()
    state = AxisState(rate=RATE)
    run_loop(mav, ScriptedKeys(["up"]), clock, hz=20.0, duration=0.25, state=state)

    # Act
    run_loop(mav, ScriptedKeys([]), clock, hz=20.0, duration=0.5, state=state)

    # Assert
    assert mav.calls[-1][3] == 400


# 25
def test_loop_last_packet_reflects_full_deflection_on_held_key() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys(["d"])

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0, state=AxisState(rate=RATE))

    # Assert
    assert mav.calls[-1][2] == 1000


def test_loop_calls_on_tick_once_per_packet() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys(["w"])
    calls: list[tuple[set[str], Mapping[str, float]]] = []

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=1.0, on_tick=lambda k, v: calls.append((k, v)))

    # Assert
    assert len(calls) == 20


def test_loop_on_tick_receives_the_currently_pressed_keys() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys(["w"])
    seen: list[set[str]] = []

    # Act
    run_loop(mav, keys, clock, hz=20.0, duration=0.05, on_tick=lambda k, v: seen.append(k))

    # Assert
    assert seen == [{"w"}]


def test_loop_stops_immediately_when_should_stop_is_already_true() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])

    # Act
    sent = run_loop(mav, keys, clock, hz=20.0, should_stop=lambda: True)

    # Assert
    assert sent == 0


def test_loop_stops_after_should_stop_flips_to_true() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])
    flips_true_after: list[bool] = [False, False, True]

    # Act
    sent = run_loop(mav, keys, clock, hz=20.0, should_stop=lambda: flips_true_after.pop(0))

    # Assert
    assert sent == 2


def test_loop_without_should_stop_ignores_it_and_runs_for_the_full_duration() -> None:
    # Arrange
    mav, clock, keys = FakeMav(), FakeClock(), ScriptedKeys([])

    # Act
    sent = run_loop(mav, keys, clock, hz=20.0, duration=0.5)

    # Assert
    assert sent == 10
