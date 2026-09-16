"""Тести `mavproxy_glue.py` — тестована частина MAVProxy-модуля keyboard_adapter,
без залежності від самого пакета `MAVProxy` (див. докстрінг модуля).
"""

from __future__ import annotations

import time

import pytest

from keyboard_adapter.mavproxy_glue import (
    MasterSender,
    is_manual_flight_mode,
    should_control,
    start_control_thread,
)
from helpers import FakeLink, ScriptedKeys


@pytest.mark.parametrize(
    ("flightmode", "expected"),
    [
        ("FBWA", True),
        ("MANUAL", False),
        ("STABILIZE", False),
        ("ACRO", False),
        ("TRAINING", False),
        ("AUTO", False),
        ("RTL", False),
        ("CIRCLE", False),
        ("GUIDED", False),
        ("UNKNOWN", False),
    ],
)
def test_is_manual_flight_mode_classifies_arduplane_modes(flightmode: str, expected: bool) -> None:
    # Arrange
    # (flightmode, expected — параметри)

    # Act
    result = is_manual_flight_mode(flightmode)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    ("flightmode", "armed", "kb_enabled", "expected"),
    [
        ("FBWA", True, True, True),
        ("FBWA", True, False, False),
        ("FBWA", False, True, False),
        ("FBWA", False, False, False),
        ("AUTO", True, True, False),
        ("RTL", True, True, False),
    ],
)
def test_should_control_requires_fbwa_and_armed_and_kb_enabled(
    flightmode: str, armed: bool, kb_enabled: bool, expected: bool
) -> None:
    # Arrange
    # (flightmode, armed, kb_enabled, expected — параметри)

    # Act
    result = should_control(flightmode, armed, kb_enabled)

    # Assert
    assert result is expected


def test_master_sender_reads_target_system_live_from_the_link() -> None:
    # Arrange
    link = FakeLink(target_system=7)
    sender = MasterSender(link)

    # Act
    sender.manual_control_send(0, 100, -200, 300, -400, 0)

    # Assert
    assert link.mav.calls == [(7, 100, -200, 300, -400, 0)]


def test_master_sender_ignores_the_target_argument_it_was_called_with() -> None:
    # Arrange
    link = FakeLink(target_system=3)
    sender = MasterSender(link)

    # Act
    sender.manual_control_send(999, 0, 0, 0, 0, 0)

    # Assert
    assert link.mav.calls[0][0] == 3


def test_master_sender_picks_up_a_target_system_that_arrives_after_construction() -> None:
    # Arrange
    link = FakeLink(target_system=0)
    sender = MasterSender(link)
    link.target_system = 1

    # Act
    sender.manual_control_send(0, 0, 0, 0, 0, 0)

    # Assert
    assert link.mav.calls[0][0] == 1


def test_start_control_thread_sends_at_least_one_packet_before_stopping() -> None:
    # Arrange
    link = FakeLink(target_system=1)
    thread, stop_event = start_control_thread(link, ScriptedKeys(["w"]), hz=20.0)
    time.sleep(0.1)

    # Act
    stop_event.set()
    thread.join(timeout=1.0)

    # Assert
    assert len(link.mav.calls) > 0


def test_start_control_thread_joins_cleanly_after_stop_event_is_set() -> None:
    # Arrange
    link = FakeLink(target_system=1)
    thread, stop_event = start_control_thread(link, ScriptedKeys([]), hz=20.0)

    # Act
    stop_event.set()
    thread.join(timeout=1.0)

    # Assert
    assert thread.is_alive() is False
