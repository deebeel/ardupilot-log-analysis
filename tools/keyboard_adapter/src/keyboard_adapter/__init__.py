from __future__ import annotations

import os
from typing import Any, Optional

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

    Клавіатурний тред живе лише коли ОДНОЧАСНО виконані три умови: апарат
    озброєний, у FBWA (єдиний режим, для якого це включено — свідомо звужено,
    без переліку "усіх ручних" режимів і без toggle-клавіш для призупинки під
    час друку команд у MAV>), і сам пілот явно ввімкнув адаптер командою
    `kb on` у консолі MAVProxy (`kb off` — вимкнути; за замовчуванням
    вимкнено). Третя умова — свідомий запобіжник: перші дві самі по собі
    (FBWA + armed) можуть настати ще на землі перед стартом чи випадково під
    час рулювання, а керування клавіатурою пілот має включати сам, не воно
    саме по собі. `mavlink_packet()` зіставляється з `self.master.flightmode`
    і `self.master.motors_armed()` — обидва поля pymavlink сам оновлює на
    кожен HEARTBEAT (`mavutil.py: mode_string_v10`/`MAV_MODE_FLAG_SAFETY_ARMED`),
    тут нічого не парситься вручну; `kb on`/`kb off` — окрема MAVProxy-команда
    (`cmd_kb`), що одразу перерахунковує стан, не чекаючи наступного HEARTBEAT.
    Дизарм чи вихід із FBWA (без зміни `kb`-прапорця) так само зупиняють
    керування — `should_control()` перевіряє усі три умови разом.

    На вхід у стан "керувати" — перевірка, чи є клавіатура (`evdev`-
    пристрій), і лише тоді старт; відсутність пристрою НЕ валить модуль, лише
    пишеться в консоль MAVProxy. Перевірка відбувається рівно в момент зміни
    режиму/арм-стану/`kb`-прапорця, не через окремий hot-plug watcher —
    підключення клавіатури ПОСЕРЕДИНІ вже активного керування навмисно нічого
    не запускає (щоб не ловити "дзвін" контактів щойно вставленого USB як
    реальні натискання; решту цього ж ризику закриває `EvdevSource.start()`,
    що скидає буфер пристрою перед початком читання).
    """
    from MAVProxy.modules.lib import mp_module

    from .evdev_source import EvdevSource, find_keyboard_device_or_none
    from .mavproxy_glue import should_control, start_control_thread

    class KeyboardAdapterModule(mp_module.MPModule):  # type: ignore[misc]
        def __init__(self, mpstate: Any) -> None:
            super(KeyboardAdapterModule, self).__init__(
                mpstate, "keyboard_adapter", "клавіатура -> MANUAL_CONTROL"
            )
            self.add_command(
                "kb", self.cmd_kb, "keyboard_adapter увімк/вимк", ["on", "off"]
            )
            self._source: Any = None
            self._thread: Any = None
            self._stop_event: Any = None
            self._kb_enabled: bool = False
            self._last_should_control: Optional[bool] = None

        def cmd_kb(self, args: Any) -> None:
            if len(args) != 1 or args[0] not in ("on", "off"):
                self.console.writeln("Використання: kb <on|off>", "red")
                return
            self._kb_enabled = args[0] == "on"
            self.console.writeln(
                "keyboard_adapter: %s" % ("увімкнено" if self._kb_enabled else "вимкнено")
            )
            self._reconsider()

        def mavlink_packet(self, m: Any) -> None:
            if m.get_type() != "HEARTBEAT":
                return
            self._reconsider()

        def _reconsider(self) -> None:
            wanted = should_control(
                self.master.flightmode, self.master.motors_armed(), self._kb_enabled
            )
            if wanted == self._last_should_control:
                return  # той самий стан, що вже був — не перепитуємо
            self._last_should_control = wanted
            if wanted:
                self._start_control()
            else:
                self._stop_control()

        def _start_control(self) -> None:
            if self._thread is not None:
                return
            device = os.environ.get("KEYBOARD_DEVICE") or find_keyboard_device_or_none()
            if device is None:
                self.console.writeln(
                    "keyboard_adapter: клавіатура не знайдена — ручне керування вимкнено",
                    "red",
                )
                return
            self._source = EvdevSource(device_path=device).start()
            self._thread, self._stop_event = start_control_thread(
                self.master, self._source.snapshot
            )

        def _stop_control(self) -> None:
            if self._thread is None:
                return
            self._stop_event.set()
            self._thread.join(timeout=1.0)
            self._source.stop()
            self._thread = None
            self._stop_event = None
            self._source = None

        def unload(self) -> None:
            self._stop_control()

    return KeyboardAdapterModule(mpstate)
