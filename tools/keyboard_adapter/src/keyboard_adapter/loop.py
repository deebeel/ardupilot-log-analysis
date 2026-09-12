"""Цикл фіксованої частоти + формування MANUAL_CONTROL.

Ні pynput, ні pymavlink тут не імпортуються: `mav`, `keys_source` і `clock` —
duck-typed залежності, тому цикл тестується фейками без мережі й реального часу.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Protocol

from .axes import AxisState, DEFAULT_RATE

DEFAULT_HZ = 20.0


class Clock(Protocol):
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


def send_manual_control(mav, values: Mapping[str, float], target: int = 0) -> None:
    """Відправити один MANUAL_CONTROL.

    `mav` — об'єкт із методом `manual_control_send` (у pymavlink це `conn.mav`).
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
    mav,
    keys_source: Callable[[], Iterable[str]],
    clock: Clock,
    hz: float = DEFAULT_HZ,
    duration: float | None = None,
    state: AxisState | None = None,
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
