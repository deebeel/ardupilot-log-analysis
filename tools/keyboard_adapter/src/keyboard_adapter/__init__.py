from __future__ import annotations

import os
from typing import Any

from .axes import AXES, DEFAULT_RATE, KEYMAP, RANGE, SPRING_AXES, AxisState, directions
from .loop import DEFAULT_HZ, run_loop, send_manual_control

__all__ = [
    "AXES",
    "AxisState",
    "DEFAULT_HZ",
    "DEFAULT_RATE",
    "KEYMAP",
    "RANGE",
    "SPRING_AXES",
    "directions",
    "init",
    "run_loop",
    "send_manual_control",
]


def init(mpstate: Any) -> Any:
    """MAVProxy `module load keyboard_adapter` entrypoint.

    Живцем виявлено (docs/host-prerequisites.md крок 3): MAVProxy's
    `load_module()` tries `MAVProxy.modules.mavproxy_<name>` first, then
    falls back to importing the BARE `<name>` itself — not `mavproxy_<name>`.
    So a third-party module reachable via `--load-module keyboard_adapter`
    must expose `init()` right here, in this package's `__init__.py`, not in
    a separately-named `mavproxy_keyboard_adapter.py` shim (that file doesn't
    exist anymore — this replaced it after a real `ERROR ... has no attribute
    'init'` on `SITL-test`).

    `MAVProxy.modules.lib.mp_module` is imported lazily, and the `MPModule`
    subclass is defined locally, so importing this package (pytest/mypy on
    macOS, no MAVProxy installed) never requires MAVProxy — only calling
    `init()`, which happens only inside a real MAVProxy process, does.
    """
    from MAVProxy.modules.lib import mp_module

    from .evdev_source import EvdevSource
    from .mavproxy_glue import start_control_thread

    class KeyboardAdapterModule(mp_module.MPModule):  # type: ignore[misc]
        def __init__(self, mpstate: Any) -> None:
            super(KeyboardAdapterModule, self).__init__(
                mpstate, "keyboard_adapter", "клавіатура -> MANUAL_CONTROL"
            )
            device = os.environ.get("KEYBOARD_DEVICE")
            self._source = EvdevSource(device_path=device)
            self._source.start()
            self._thread, self._stop_event = start_control_thread(
                self.master, self._source.snapshot
            )

        def unload(self) -> None:
            self._stop_event.set()
            self._thread.join(timeout=1.0)
            self._source.stop()

    return KeyboardAdapterModule(mpstate)
