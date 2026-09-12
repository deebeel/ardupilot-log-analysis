"""Хелпери й фейки для тестів — уся ітерація/умови живуть тут, не в тілах тестів."""

from __future__ import annotations

from typing import Iterable, Mapping

from keyboard_adapter.axes import AxisState


def advance(state: AxisState, dt: float, keys: Iterable[str], n: int = 1) -> Mapping[str, float]:
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
        self.calls: list[tuple] = []

    def manual_control_send(self, target, x, y, z, r, buttons) -> None:
        self.calls.append((target, x, y, z, r, buttons))


class FakeClock:
    """Керований годинник: `sleep` просто рухає час уперед."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class ScriptedKeys:
    """keys_source, що віддає той самий набір клавіш на кожен виклик."""

    def __init__(self, keys: Iterable[str] = ()) -> None:
        self.keys = list(keys)
        self.calls = 0

    def __call__(self) -> list[str]:
        self.calls += 1
        return list(self.keys)
