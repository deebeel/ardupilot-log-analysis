"""Хелпери й фейки для тестів — уся ітерація/умови живуть тут, не в тілах тестів.

Фейки навмисно нічого не наслідують: mypy перевіряє їх структурну відповідність
протоколам `loop.ManualControlSender` / `loop.Clock` / `loop.KeysSource` через
явні анотації в `_PROTOCOL_CONFORMANCE` нижче.
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, Tuple

from keyboard_adapter.axes import AxisState
from keyboard_adapter.loop import Clock, KeysSource, ManualControlSender
from keyboard_adapter.mavproxy_glue import MavlinkLink

ManualControlCall = Tuple[int, int, int, int, int, int]


def advance(
    state: AxisState, dt: float, keys: Iterable[str], n: int = 1
) -> Mapping[str, float]:
    """Прогнати `n` кроків симуляції по `dt` з фіксованим набором клавіш."""
    values: Mapping[str, float] = dict(state.values)
    for _ in range(n):
        values = state.step(dt, keys)
    return values


def steps_to_zero(state: AxisState, dt: float, axis: str, limit: int = 1000) -> int:
    """Скільки кроків spring-return потрібно, щоб вісь стала рівно 0."""
    for i in range(1, limit + 1):
        state.step(dt, [])
        if state.values[axis] == 0.0:
            return i
    return -1


class FakeMav:
    """Замість `conn.mav` — записує всі manual_control_send."""

    def __init__(self) -> None:
        self.calls: List[ManualControlCall] = []

    def manual_control_send(
        self, target: int, x: int, y: int, z: int, r: int, buttons: int
    ) -> None:
        self.calls.append((target, x, y, z, r, buttons))


class FakeClock:
    """Керований годинник: `sleep` просто рухає час уперед."""

    def __init__(self, start: float = 0.0) -> None:
        self.now: float = start

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class ScriptedKeys:
    """keys_source, що віддає той самий набір клавіш на кожен виклик."""

    def __init__(self, keys: Iterable[str] = ()) -> None:
        self.keys: List[str] = list(keys)
        self.calls: int = 0

    def __call__(self) -> List[str]:
        self.calls += 1
        return list(self.keys)


class FakeLink:
    """Замість `self.master` у MAVProxy-модулі — `target_system` змінний після
    створення, щоб симулювати heartbeat апарата, що приходить пізніше."""

    def __init__(self, target_system: int = 0) -> None:
        self.target_system: int = target_system
        self.mav: FakeMav = FakeMav()


# Статична перевірка: фейки структурно задовольняють протоколи loop.py/mavproxy_glue.py.
_PROTOCOL_CONFORMANCE: Tuple[ManualControlSender, Clock, KeysSource, MavlinkLink] = (
    FakeMav(),
    FakeClock(),
    ScriptedKeys(),
    FakeLink(),
)
