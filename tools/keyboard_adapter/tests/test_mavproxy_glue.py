"""Тести `mavproxy_glue.py` — тестована частина MAVProxy-модуля keyboard_adapter,
без залежності від самого пакета `MAVProxy` (див. докстрінг модуля).
"""

from __future__ import annotations

import time

from keyboard_adapter.mavproxy_glue import MasterSender, start_control_thread
from helpers import FakeLink, ScriptedKeys


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
