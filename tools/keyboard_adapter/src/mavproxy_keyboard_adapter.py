"""MAVProxy-модуль: клавіатура -> MANUAL_CONTROL, замість окремого процесу.

Свідомий вибір архітектури (див. CLAUDE.md): керування живе В ПРОЦЕСІ
MAVProxy, як звичайний MAVProxy-модуль, а не окремим процесом з власним UDP-
конектом до SITL. Ідіоматично для MAVProxy — модулі саме так і розширюють
функціонал (map/console/antenna-tracker тощо), і не потребує окремого
`--connect`/heartbeat-очікування: `self.master` уже підключений.

Тонкий shim НАВМИСНО — уся тестована логіка (тред, адаптація лінка,
кооперативна зупинка) в `keyboard_adapter.mavproxy_glue`, без залежності
від пакета `MAVProxy` (той є лише в ArduPilot-оточенні на Ubuntu-хості,
`tools/prereqs.sh`, не в dev-оточенні цього репозиторію). MAVProxy шукає
модулі за іменем файлу (`mavproxy_<name>.py`) на `PYTHONPATH` — тому цей
файл лежить у `src/` поряд із пакетом `keyboard_adapter/`, не всередині
нього; `run-sitl.sh` додає `tools/keyboard_adapter/src` у `PYTHONPATH`
MAVProxy і вантажить модуль через `sim_vehicle.py --mavproxy-args
"--load-module keyboard_adapter"`.

**[не перевірено живцем]** написано за задокументованими конвенціями
MAVProxy-модулів (MPModule, self.master, unload()) — перший реальний прогін
на Ubuntu-хості ще належить зробити (docs/host-prerequisites.md, крок 4).

СВІДОМИЙ КОМПРОМІС: якщо сам процес MAVProxy впаде — впаде й керування
(на відміну від попередньої схеми з окремим процесом). Це стосується лише
повного краху процесу: падіння ОДНОГО модуля (map/console) не тягне за
собою інші завантажені модулі — керування клавіатурою продовжує йти
"наосліп" (без HUD/мапи), доки живий сам процес MAVProxy.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from MAVProxy.modules.lib import mp_module

from keyboard_adapter.evdev_source import EvdevSource
from keyboard_adapter.mavproxy_glue import start_control_thread

#: Явний пристрій замість автовизначення (перший з KEY_A) — на випадок, якщо
#: автовизначення обрало не той /dev/input/eventN. env-змінна, не аргумент
#: модуля: MAVProxy `--load-module` не має зручного способу передати іменовані
#: опції в конструктор модуля.
_DEVICE: Optional[str] = os.environ.get("KEYBOARD_DEVICE")


class KeyboardAdapterModule(mp_module.MPModule):  # type: ignore[misc]
    def __init__(self, mpstate: Any) -> None:
        super(KeyboardAdapterModule, self).__init__(
            mpstate, "keyboard_adapter", "клавіатура -> MANUAL_CONTROL"
        )
        self._source = EvdevSource(device_path=_DEVICE)
        self._source.start()
        self._thread, self._stop_event = start_control_thread(self.master, self._source.snapshot)

    def unload(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._source.stop()
