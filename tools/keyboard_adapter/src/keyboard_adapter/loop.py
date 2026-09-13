"""Цикл фіксованої частоти + формування MANUAL_CONTROL.

Ні pynput, ні pymavlink тут не імпортуються: `mav`, `keys_source` і `clock` описані
структурними протоколами, тому цикл тестується фейками без мережі й реального часу.
"""

from __future__ import annotations

from typing import Final, Iterable, Mapping, Optional, Protocol, runtime_checkable

from .axes import DEFAULT_RATE, AxisState

DEFAULT_HZ: Final[float] = 20.0


@runtime_checkable
class ManualControlSender(Protocol):
    """Те, що вміє `conn.mav` у pymavlink — рівно один потрібний нам метод."""

    def manual_control_send(
        self, target: int, x: int, y: int, z: int, r: int, buttons: int
    ) -> None: ...


@runtime_checkable
class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


@runtime_checkable
class KeysSource(Protocol):
    """Викликається раз на пакет і повертає поточний набір натиснутих клавіш."""

    def __call__(self) -> Iterable[str]: ...


def send_manual_control(
    mav: ManualControlSender, values: Mapping[str, float], target: int = 0
) -> None:
    """Відправити один MANUAL_CONTROL.

    Відповідність осей MAVLink: x=pitch, y=roll, z=throttle, r=yaw.
    """
    mav.manual_control_send(
        target,
        int(values["pitch"]),
        int(values["roll"]),
        int(values["throttle"]),
        int(values["yaw"]),
        0,
    )


def run_loop(
    mav: ManualControlSender,
    keys_source: KeysSource,
    clock: Clock,
    hz: float = DEFAULT_HZ,
    duration: Optional[float] = None,
    state: Optional[AxisState] = None,
    rate: float = DEFAULT_RATE,
    target: int = 0,
) -> int:
    """Слати MANUAL_CONTROL із частотою `hz` незалежно від подій клавіатури.

    `duration=None` — нескінченно. Повертає кількість відправлених пакетів.
    """
    period = 1.0 / hz
    state = state if state is not None else AxisState(rate=rate)
    total = None if duration is None else int(round(duration * hz))

    start = clock.monotonic()
    prev = start
    sent = 0
    while total is None or sent < total:
        now = clock.monotonic()
        values = state.step(now - prev, keys_source())
        prev = now
        send_manual_control(mav, values, target=target)
        sent += 1
        clock.sleep(max(0.0, start + sent * period - clock.monotonic()))
    return sent
