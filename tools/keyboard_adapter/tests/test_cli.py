"""Тести `cli.parse_args`/`NullManualControlSender` — без запуску `main()` (той
лізе в мережу/pymavlink і блокує на реальному циклі клавіш).
"""

from __future__ import annotations

import pytest

from keyboard_adapter.cli import NullManualControlSender, TickPrinter, parse_args


def test_parse_args_defaults_to_no_dry_run() -> None:
    # Arrange / Act
    args = parse_args([])

    # Assert
    assert args.dry is False


def test_parse_args_accepts_dry_flag() -> None:
    # Arrange / Act
    args = parse_args(["--dry"])

    # Assert
    assert args.dry is True


def test_parse_args_defaults_to_no_debug_output() -> None:
    # Arrange / Act
    args = parse_args([])

    # Assert
    assert args.debug is False


def test_null_manual_control_sender_accepts_a_call_without_raising() -> None:
    # Arrange
    sender = NullManualControlSender()

    # Act / Assert (немає що перевіряти окрім відсутності винятку — сенс класу)
    sender.manual_control_send(1, 2, 3, 4, 5, 6)


def test_tick_printer_prints_on_the_first_call(capsys: pytest.CaptureFixture[str]) -> None:
    # Arrange
    printer = TickPrinter(min_interval_s=0.1, now=lambda: 10.0)

    # Act
    printer({"w"}, {"pitch": 500.0, "roll": 0.0, "yaw": 0.0, "throttle": 0.0})

    # Assert
    assert "pitch=  500" in capsys.readouterr().out


def test_tick_printer_skips_a_call_inside_the_throttle_window(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    times = iter([10.0, 10.05])
    printer = TickPrinter(min_interval_s=0.1, now=lambda: next(times))
    printer(set(), {"pitch": 0.0, "roll": 0.0, "yaw": 0.0, "throttle": 0.0})
    capsys.readouterr()

    # Act
    printer({"w"}, {"pitch": 500.0, "roll": 0.0, "yaw": 0.0, "throttle": 0.0})

    # Assert
    assert capsys.readouterr().out == ""


def test_tick_printer_prints_again_after_the_throttle_window_elapses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    times = iter([10.0, 10.2])
    printer = TickPrinter(min_interval_s=0.1, now=lambda: next(times))
    printer(set(), {"pitch": 0.0, "roll": 0.0, "yaw": 0.0, "throttle": 0.0})
    capsys.readouterr()

    # Act
    printer({"w"}, {"pitch": 500.0, "roll": 0.0, "yaw": 0.0, "throttle": 0.0})

    # Assert
    assert "pitch=  500" in capsys.readouterr().out
