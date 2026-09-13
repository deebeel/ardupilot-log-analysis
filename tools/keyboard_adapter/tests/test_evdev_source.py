"""§TEST-PLAN "Сценарії — evdev_source.py (Wayland-бекенд)"."""

from __future__ import annotations

import sys

import pytest

from evdev_fakes import FakeEcodes, FakeEvdevModule, FakeEvent, FakeInputDevice
from keyboard_adapter.evdev_source import (
    EV_KEY,
    KEY_DOWN,
    KEY_REPEAT,
    KEY_UP,
    EvdevSource,
    find_keyboard_device,
    normalize_evdev,
)

KEY_W = 17
KEY_A = 30
KEY_LEFTSHIFT = 42
KEY_RIGHTSHIFT = 54
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97
KEY_ESC = 1
EV_SYN = 0


# --- E1-E5: normalize_evdev -------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (KEY_W, "w"),
        (KEY_A, "a"),
        (KEY_LEFTSHIFT, "shift"),
        (KEY_RIGHTSHIFT, "shift"),
        (KEY_LEFTCTRL, "ctrl"),
        (KEY_RIGHTCTRL, "ctrl"),
    ],
)
def test_normalize_evdev_maps_known_codes(code: int, expected: str) -> None:
    # Arrange
    # (code, expected — параметри)

    # Act
    result = normalize_evdev(code)

    # Assert
    assert result == expected


def test_normalize_evdev_unknown_code_is_none() -> None:
    # Arrange
    code = KEY_ESC

    # Act
    result = normalize_evdev(code)

    # Assert
    assert result is None


# --- E6-E10: EvdevSource.feed ------------------------------------------------


def test_feed_key_down_adds_to_snapshot() -> None:
    # Arrange
    source = EvdevSource()

    # Act
    source.feed(KEY_W, KEY_DOWN)

    # Assert
    assert source.snapshot() == {"w"}


def test_feed_key_up_after_down_clears_snapshot() -> None:
    # Arrange
    source = EvdevSource()
    source.feed(KEY_W, KEY_DOWN)

    # Act
    source.feed(KEY_W, KEY_UP)

    # Assert
    assert source.snapshot() == set()


def test_feed_repeat_without_prior_down_does_not_add() -> None:
    # Arrange
    source = EvdevSource()

    # Act
    source.feed(KEY_W, KEY_REPEAT)

    # Assert
    assert source.snapshot() == set()


def test_feed_repeat_after_down_keeps_key_pressed() -> None:
    # Arrange
    source = EvdevSource()
    source.feed(KEY_W, KEY_DOWN)

    # Act
    source.feed(KEY_W, KEY_REPEAT)

    # Assert
    assert source.snapshot() == {"w"}


def test_feed_unknown_code_down_does_not_add() -> None:
    # Arrange
    source = EvdevSource()

    # Act
    source.feed(KEY_ESC, KEY_DOWN)

    # Assert
    assert source.snapshot() == set()


# --- E11-E12: EvdevSource._run -----------------------------------------------


def test_run_drives_feed_from_finite_event_stream() -> None:
    # Arrange
    source = EvdevSource()
    device = FakeInputDevice(
        capabilities={},
        events=[
            FakeEvent(EV_KEY, KEY_W, KEY_DOWN),
            FakeEvent(EV_KEY, 31, KEY_DOWN),  # KEY_S
            FakeEvent(EV_KEY, 31, KEY_UP),
        ],
    )

    # Act
    source._run(device)

    # Assert
    assert source.snapshot() == {"w"}


def test_run_ignores_non_key_events() -> None:
    # Arrange
    source = EvdevSource()
    device = FakeInputDevice(
        capabilities={},
        events=[FakeEvent(EV_SYN, 0, 0), FakeEvent(EV_KEY, KEY_W, KEY_DOWN)],
    )

    # Act
    source._run(device)

    # Assert
    assert source.snapshot() == {"w"}


# --- E13: EvdevSource.stop ----------------------------------------------------


def test_stop_closes_device_and_sets_stop_event() -> None:
    # Arrange
    source = EvdevSource()
    device = FakeInputDevice(capabilities={})
    source._device = device

    # Act
    source.stop()

    # Assert
    assert device.closed is True


def test_stop_sets_stop_event_flag() -> None:
    # Arrange
    source = EvdevSource()
    device = FakeInputDevice(capabilities={})
    source._device = device

    # Act
    source.stop()

    # Assert
    assert source._stop_event.is_set() is True


# --- E14-E16: find_keyboard_device --------------------------------------------


def test_find_keyboard_device_returns_path_with_key_a(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    keyboard = FakeInputDevice(capabilities={FakeEcodes.EV_KEY: [KEY_A, KEY_W]})
    fake_module = FakeEvdevModule(devices={"/dev/input/event3": keyboard})
    monkeypatch.setitem(sys.modules, "evdev", fake_module)

    # Act
    result = find_keyboard_device()

    # Assert
    assert result == "/dev/input/event3"


def test_find_keyboard_device_raises_when_no_device_has_key_a(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    mouse = FakeInputDevice(capabilities={FakeEcodes.EV_KEY: [272]})  # BTN_LEFT, не KEY_A
    fake_module = FakeEvdevModule(devices={"/dev/input/event0": mouse})
    monkeypatch.setitem(sys.modules, "evdev", fake_module)

    # Act
    with pytest.raises(RuntimeError, match="input") as excinfo:
        find_keyboard_device()

    # Assert
    assert "input" in str(excinfo.value)


def test_find_keyboard_device_returns_first_match_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    first = FakeInputDevice(capabilities={FakeEcodes.EV_KEY: [KEY_A]})
    second = FakeInputDevice(capabilities={FakeEcodes.EV_KEY: [KEY_A]})
    fake_module = FakeEvdevModule(
        devices={"/dev/input/event1": first, "/dev/input/event2": second}
    )
    monkeypatch.setitem(sys.modules, "evdev", fake_module)

    # Act
    result = find_keyboard_device()

    # Assert
    assert result == "/dev/input/event1"


# --- E17-E18: EvdevSource.start -----------------------------------------------


def test_start_with_explicit_device_path_skips_autodetect(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    device = FakeInputDevice(
        capabilities={},
        events=[FakeEvent(EV_KEY, KEY_W, KEY_DOWN)],
    )
    fake_module = FakeEvdevModule(
        devices={"/dev/input/event5": device}, forbid_list_devices=True
    )
    monkeypatch.setitem(sys.modules, "evdev", fake_module)
    source = EvdevSource(device_path="/dev/input/event5")

    # Act
    source.start()
    source.join(timeout=1.0)

    # Assert
    assert source.snapshot() == {"w"}


def test_start_without_device_path_autodetects(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    keyboard = FakeInputDevice(
        capabilities={FakeEcodes.EV_KEY: [KEY_A]},
        events=[FakeEvent(EV_KEY, KEY_W, KEY_DOWN)],
    )
    fake_module = FakeEvdevModule(devices={"/dev/input/event7": keyboard})
    monkeypatch.setitem(sys.modules, "evdev", fake_module)
    source = EvdevSource()

    # Act
    source.start()
    source.join(timeout=1.0)

    # Assert
    assert source.snapshot() == {"w"}
