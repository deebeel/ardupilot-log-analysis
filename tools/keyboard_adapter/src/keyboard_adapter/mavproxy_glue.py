"""Тестована частина MAVProxy-модуля `keyboard_adapter`.

Ні тут, ні в `loop.py`/`axes.py` не імпортується сам пакет `MAVProxy` — той
ставиться лише разом з ArduPilot на Ubuntu-хості (`tools/prereqs.sh`), не в
dev-оточенні цього репозиторію. `__init__.py`'s `init()` (лінива імпортація
`MAVProxy.modules.lib.mp_module.MPModule`, локальний підклас) — єдине місце,
що реально залежить від MAVProxy; уся логіка життєвого циклу фонового треду
і адаптації MAVProxy-лінка тестується тут.
"""

from __future__ import annotations

import threading
import time
from typing import Final, FrozenSet, Protocol

from .axes import DEFAULT_RATE, AxisState
from .loop import DEFAULT_HZ, KeysSource, ManualControlSender, run_loop

#: Єдиний режим ArduPlane, де клавіатурний ввід реально включається — свідомо
#: звужено до самого FBWA (не весь набір "ручних" режимів), за прямим
#: запитом: простіше й передбачуваніше, ніж підтримувати список і toggle-
#: клавіші для призупинки під час друку команд у MAV>. Звірено з
#: `master.flightmode` (pymavlink сам оновлює це поле на кожен HEARTBEAT,
#: `mavutil.py: mode_string_v10`) — модуль лише читає, нічого не парсить сам.
MANUAL_FLIGHT_MODES: Final[FrozenSet[str]] = frozenset({"FBWA"})


def is_manual_flight_mode(flightmode: str) -> bool:
    return flightmode in MANUAL_FLIGHT_MODES


def should_control(flightmode: str, armed: bool, kb_enabled: bool) -> bool:
    """Чи має клавіатурний тред зараз слати `MANUAL_CONTROL`.

    Три незалежні ворота, усі мають виконуватись одночасно: `FBWA` +
    озброєний (як і раніше — вихід із FBWA в будь-який інший режим І дизарм,
    навіть без зміни режиму, однаково зупиняють керування) + `kb_enabled`
    (явний `kb on`/`kb off` у консолі MAVProxy — за замовчуванням `False`,
    тобто адаптер НЕ підхоплює керування сам щойно виконались перші дві
    умови, доки пілот не ввімкне його свідомо)."""
    return is_manual_flight_mode(flightmode) and armed and kb_enabled


class MavlinkLink(Protocol):
    """Мінімум `self.master` у MAVProxy-модулі (обраний GCS-лінк), потрібний тут.

    `mav` — read-only `@property` у протоколі (не звичайний атрибут), щоб
    конкретні лінки/фейки з ковариантним типом `.mav` (напр. `FakeMav`
    замість голого `ManualControlSender`) проходили структурну перевірку —
    mypy інакше вимагає інваріантності для мутабельних атрибутів."""

    target_system: int

    @property
    def mav(self) -> ManualControlSender: ...


class MasterSender:
    """Адаптує MAVProxy-лінк під `loop.ManualControlSender`.

    Не читає `target_system` один раз у конструкторі (як робив
    `cli.wait_for_vehicle_heartbeat` для окремого UDP-конекту) — модуль
    вантажиться разом з MAVProxy, ще до підключення апарата, тож на момент
    старту фонового треду `target_system` майже напевно `0`. Читає з живого
    `link.target_system` щопакета: щойно MAVProxy отримає heartbeat апарата
    (сам оновлює це поле), наступний-таки пакет піде з правильним `target`
    без окремого очікування.
    """

    def __init__(self, link: MavlinkLink) -> None:
        self._link = link

    def manual_control_send(
        self, target: int, x: int, y: int, z: int, r: int, buttons: int
    ) -> None:
        self._link.mav.manual_control_send(self._link.target_system, x, y, z, r, buttons)


class SystemClock:
    """Реалізація протоколу `loop.Clock` на системному годиннику."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def start_control_thread(
    link: MavlinkLink,
    keys_source: KeysSource,
    hz: float = DEFAULT_HZ,
    rate: float = DEFAULT_RATE,
) -> "tuple[threading.Thread, threading.Event]":
    """Запустити `run_loop` у власному фоновому треді — незалежно від idle-loop
    MAVProxy (карта/консоль/інші модулі не впливають на 20 Гц такт).

    Повертає `(thread, stop_event)`: `unload()` модуля виставляє `stop_event`
    (кооперативна зупинка — `run_loop`'s `should_stop`) і приєднує `thread`.
    """
    stop_event = threading.Event()
    thread = threading.Thread(
        target=lambda: run_loop(
            MasterSender(link),
            keys_source,
            SystemClock(),
            hz=hz,
            state=AxisState(rate=rate),
            should_stop=stop_event.is_set,
        ),
        daemon=True,
        name="keyboard-adapter",
    )
    thread.start()
    return thread, stop_event
