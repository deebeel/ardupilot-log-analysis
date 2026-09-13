"""Фейки модуля `evdev` для тестів `evdev_source.py` без реального пристрою/потоку.

`evdev` — лінукс-специфічний пакет (немає на macOS/CI), тому підмінюється в
`sys.modules["evdev"]` ще до виклику коду з локальним `import evdev` — той
резолвиться на фейк, реального пакета не потребує.
"""

from __future__ import annotations

from typing import Dict, Iterable, List


class FakeEvent:
    """Відповідає мінімуму `evdev_source.InputEventLike`."""

    def __init__(self, type_: int, code: int, value: int) -> None:
        self.type: int = type_
        self.code: int = code
        self.value: int = value


class FakeInputDevice:
    """Відповідає мінімуму `evdev_source.Device`."""

    def __init__(
        self,
        capabilities: Dict[int, List[int]],
        events: Iterable[FakeEvent] = (),
    ) -> None:
        self._capabilities: Dict[int, List[int]] = capabilities
        self._events: List[FakeEvent] = list(events)
        self.closed: bool = False

    def capabilities(self) -> Dict[int, List[int]]:
        return self._capabilities

    def read_loop(self) -> Iterable[FakeEvent]:
        return iter(self._events)

    def close(self) -> None:
        self.closed = True


class FakeEcodes:
    EV_KEY: int = 1
    KEY_A: int = 30


class FakeEvdevModule:
    """Підміна модуля `evdev`: `list_devices()` + `InputDevice(path)` за реєстром.

    `forbid_list_devices=True` перетворює виклик `list_devices()` на провал
    тесту — використовується для перевірки, що явний `device_path` не запускає
    автовизначення (сценарій E17 TEST-PLAN).
    """

    def __init__(
        self,
        devices: Dict[str, FakeInputDevice],
        forbid_list_devices: bool = False,
    ) -> None:
        self._devices: Dict[str, FakeInputDevice] = devices
        self._forbid_list_devices: bool = forbid_list_devices
        self.ecodes = FakeEcodes

    def list_devices(self) -> List[str]:
        assert not self._forbid_list_devices, (
            "list_devices() не мав викликатись — device_path заданий явно"
        )
        return list(self._devices.keys())

    def InputDevice(self, path: str) -> FakeInputDevice:  # noqa: N802 - ім'я реального evdev API
        return self._devices[path]
