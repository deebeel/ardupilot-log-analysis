"""Тонка обгортка над pynput: тримає множину натиснутих клавіш.

pynput імпортується всередині `start()`, а не на рівні модуля — на macOS/headless
імпорт може впасти через дозволи, і це не повинно ламати ні тести, ні імпорт пакета.
"""

from __future__ import annotations

import threading


class KeyboardSource:
    """Джерело натиснутих клавіш у вигляді нормалізованих рядків."""

    def __init__(self) -> None:
        self._pressed: set[str] = set()
        self._lock = threading.Lock()
        self._listener = None

    # --- нормалізація подій pynput ---------------------------------------
    @staticmethod
    def normalize(key) -> str | None:
        char = getattr(key, "char", None)
        if char:
            return char.lower()
        name = getattr(key, "name", None)
        if not name:
            return None
        name = name.lower()
        if name.startswith("shift"):
            return "shift"
        if name.startswith("ctrl"):
            return "ctrl"
        return name

    def press(self, key) -> None:
        name = self.normalize(key)
        if name is None:
            return
        with self._lock:
            self._pressed.add(name)

    def release(self, key) -> None:
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

        self._listener = pynput_keyboard.Listener(
            on_press=self.press, on_release=self.release
        )
        self._listener.start()
        return self

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
