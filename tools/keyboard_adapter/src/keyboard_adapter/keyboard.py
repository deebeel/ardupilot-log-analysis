"""Тонка обгортка над pynput: тримає множину натиснутих клавіш.

pynput імпортується всередині `start()`, а не на рівні модуля — на macOS/headless
імпорт може впасти через дозволи, і це не повинно ламати ні тести, ні імпорт пакета.
"""

from __future__ import annotations

import threading
from typing import Optional, Protocol


class Listener(Protocol):
    """Мінімум, що ми використовуємо від `pynput.keyboard.Listener`."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


class KeyboardSource:
    """Джерело натиснутих клавіш у вигляді нормалізованих рядків."""

    def __init__(self) -> None:
        self._pressed: set[str] = set()
        self._lock: threading.Lock = threading.Lock()
        self._listener: Optional[Listener] = None

    # --- нормалізація подій pynput ---------------------------------------
    @staticmethod
    def normalize(key: object) -> Optional[str]:
        char: object = getattr(key, "char", None)
        if isinstance(char, str) and char:
            return char.lower()
        raw: object = getattr(key, "name", None)
        if not isinstance(raw, str) or not raw:
            return None
        name = raw.lower()
        if name.startswith("shift"):
            return "shift"
        if name.startswith("ctrl"):
            return "ctrl"
        return name

    def press(self, key: object) -> None:
        name = self.normalize(key)
        if name is None:
            return
        with self._lock:
            self._pressed.add(name)

    def release(self, key: object) -> None:
        name = self.normalize(key)
        if name is None:
            return
        with self._lock:
            self._pressed.discard(name)

    def snapshot(self) -> set[str]:
        with self._lock:
            return set(self._pressed)

    # --- I/O --------------------------------------------------------------
    def start(self) -> "KeyboardSource":
        from pynput import keyboard as pynput_keyboard  # локальний імпорт — див. docstring

        listener: Listener = pynput_keyboard.Listener(
            on_press=self.press, on_release=self.release
        )
        self._listener = listener
        listener.start()
        return self

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
