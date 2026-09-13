"""evdev-бекенд клавіатури: читає `/dev/input/eventN` напряму.

Працює однаково на Xorg і Wayland — на відміну від `pynput` (X11 global-grab,
якого Wayland свідомо не надає застосункам), `evdev` читає з kernel input
layer, того самого рівня, звідки дані бере сам дисплейний сервер. Потребує
членства в групі `input` (`sudo usermod -aG input $USER`, релогін) і працює
лише на Linux — пакет `evdev` не встановлюється на macOS (env-маркер у
`pyproject.toml`), тому `evdev` імпортується ЛИШЕ всередині функцій, що
реально відкривають пристрій (`start()`, `find_keyboard_device()`); сам
модуль лишається імпортовним і тестовним на будь-якій платформі.

Відоме обмеження (той самий клас компромісу, що й `directions()` в `axes.py`
для протилежних клавіш): обидва фізичні Shift і обидва Ctrl мапляться на ОДНЕ
логічне ім'я (`"shift"`/`"ctrl"`), тому одночасне натискання Left+Right Shift
з наступним відпусканням лише одного з них передчасно зніме "shift" зі стану.
Для клавіатурного керування літаком це не сценарій польоту.
"""

from __future__ import annotations

import threading
from typing import Final, Iterable, List, Optional, Protocol

#: код клавіші evdev (Linux `input-event-codes.h`) -> нормалізована назва,
#: як очікує `keyboard_adapter.axes.KEYMAP`. Захардкоджено числами (не
#: `evdev.ecodes.KEY_W` тощо), щоб модуль лишався імпортовним і тестовним
#: без встановленого `evdev` (macOS, CI).
KEYCODE_TO_NAME: Final[dict[int, str]] = {
    17: "w",  # KEY_W
    31: "s",  # KEY_S
    30: "a",  # KEY_A
    32: "d",  # KEY_D
    16: "q",  # KEY_Q
    18: "e",  # KEY_E
    42: "shift",  # KEY_LEFTSHIFT
    54: "shift",  # KEY_RIGHTSHIFT
    29: "ctrl",  # KEY_LEFTCTRL
    97: "ctrl",  # KEY_RIGHTCTRL
}

#: `InputEvent.type` для клавіатурних подій (`EV_KEY` у Linux `input.h`).
EV_KEY: Final[int] = 1

#: `InputEvent.value`: 0 — відпущено, 1 — натиснуто, 2 — автоповтор утримання.
KEY_UP: Final[int] = 0
KEY_DOWN: Final[int] = 1
KEY_REPEAT: Final[int] = 2


def normalize_evdev(code: int) -> Optional[str]:
    """Код клавіші evdev -> нормалізована назва, або `None`, якщо поза KEYMAP."""
    return KEYCODE_TO_NAME.get(code)


class InputEventLike(Protocol):
    type: int
    code: int
    value: int


class Device(Protocol):
    """Мінімум, що ми використовуємо від `evdev.InputDevice`."""

    def read_loop(self) -> Iterable[InputEventLike]: ...

    def close(self) -> None: ...


def find_keyboard_device() -> str:
    """Перший пристрій у `/dev/input`, серед можливостей якого є `KEY_A`.

    Проста й достатня евристика: миші/тачпади не вміють `KEY_A`, а справжні
    клавіатури — вміють. Піднімає `RuntimeError` з підказкою, якщо нічого не
    знайдено (найчастіша причина — користувач не в групі `input`).
    """
    import evdev  # локальний імпорт — див. докстрінг модуля

    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        keys = device.capabilities().get(evdev.ecodes.EV_KEY, [])
        if evdev.ecodes.KEY_A in keys:
            return str(path)
    raise RuntimeError(
        "Не знайдено клавіатурний пристрій у /dev/input. Перевірте членство в "
        "групі `input` (sudo usermod -aG input $USER, потім релогін) або "
        "вкажіть пристрій явно через --device (див. ls /dev/input/by-id/)."
    )


class EvdevSource:
    """Джерело натиснутих клавіш: читає один evdev-пристрій у фоновому потоці."""

    def __init__(self, device_path: Optional[str] = None) -> None:
        self._device_path: Optional[str] = device_path
        self._pressed: set[str] = set()
        self._lock: threading.Lock = threading.Lock()
        self._device: Optional[Device] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()

    def feed(self, code: int, value: int) -> None:
        """Застосувати одну подію клавіші до поточного стану.

        `KEY_REPEAT` навмисно ігнорується: клавіша вже позначена натиснутою
        по `KEY_DOWN`, повторний код нічого нового не додає.
        """
        name = normalize_evdev(code)
        if name is None or value == KEY_REPEAT:
            return
        if value == KEY_DOWN:
            with self._lock:
                self._pressed.add(name)
        elif value == KEY_UP:
            with self._lock:
                self._pressed.discard(name)

    def snapshot(self) -> set[str]:
        with self._lock:
            return set(self._pressed)

    def _run(self, device: Device) -> None:
        for event in device.read_loop():
            if self._stop_event.is_set():
                return
            if event.type == EV_KEY:
                self.feed(event.code, event.value)

    def start(self) -> "EvdevSource":
        import evdev  # локальний імпорт — див. докстрінг модуля

        path = self._device_path or find_keyboard_device()
        device: Device = evdev.InputDevice(path)
        self._device = device
        thread = threading.Thread(target=self._run, args=(device,), daemon=True)
        self._thread = thread
        thread.start()
        return self

    def stop(self) -> None:
        self._stop_event.set()
        if self._device is not None:
            self._device.close()
        self.join(timeout=1.0)

    def join(self, timeout: Optional[float] = None) -> None:
        """Дочекатися завершення фонового потоку.

        У проді потік читає з реального пристрою й сам не завершується — тут
        корисно лише зі скінченним потоком подій (тести) або після `stop()`.
        No-op, якщо потік ще не запущено.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)


__all__: List[str] = [
    "EV_KEY",
    "KEY_DOWN",
    "KEY_REPEAT",
    "KEY_UP",
    "KEYCODE_TO_NAME",
    "EvdevSource",
    "find_keyboard_device",
    "normalize_evdev",
]
