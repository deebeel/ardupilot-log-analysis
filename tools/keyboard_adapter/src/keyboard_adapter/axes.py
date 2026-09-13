"""Чиста логіка осей керування — без pynput і без pymavlink.

Модель (docs/implementation-plan.md §4):
- roll/pitch/yaw: `value += k*dt` поки натиснута клавіша, інакше плавне повернення
  до нуля з тим самим `k` (spring-return), без проскакування через нуль;
- throttle: наростає/спадає під натиском, але після відпускання **утримується**;
- усе кліпається в [-RANGE, RANGE] — діапазон MAVLink MANUAL_CONTROL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Iterable, Mapping

RANGE: Final[float] = 1000.0
DEFAULT_RATE: Final[float] = 2000.0  # одиниць/с: 0 → 1000 за 0.5 с

AXES: Final[tuple[str, ...]] = ("roll", "pitch", "yaw", "throttle")
SPRING_AXES: Final[tuple[str, ...]] = ("roll", "pitch", "yaw")

#: клавіша → (вісь, знак)
KEYMAP: Final[dict[str, tuple[str, int]]] = {
    "w": ("pitch", +1),
    "s": ("pitch", -1),
    "d": ("roll", +1),
    "a": ("roll", -1),
    "e": ("yaw", +1),
    "q": ("yaw", -1),
    "shift": ("throttle", +1),
    "ctrl": ("throttle", -1),
}


def _clip(value: float) -> float:
    return max(-RANGE, min(RANGE, value))


def directions(pressed_keys: Iterable[str]) -> dict[str, int]:
    """Нетто-напрямок кожної осі з набору натиснутих клавіш.

    Протилежні клавіші (A+D) взаємно гасяться → 0.
    """
    result = {axis: 0 for axis in AXES}
    for key in pressed_keys:
        mapped = KEYMAP.get(str(key).lower())
        if mapped is None:
            continue
        axis, sign = mapped
        result[axis] += sign
    return {axis: max(-1, min(1, value)) for axis, value in result.items()}


@dataclass
class AxisState:
    """Стан чотирьох осей; `step` — єдина точка зміни."""

    rate: float = DEFAULT_RATE
    values: dict[str, float] = field(
        default_factory=lambda: {axis: 0.0 for axis in AXES}
    )

    def step(self, dt: float, pressed_keys: Iterable[str]) -> Mapping[str, float]:
        """Просунути стан на `dt` секунд. Повертає копію поточних значень."""
        if dt <= 0:  # dt=0 або стрибок годинника назад — стан не змінюємо
            return dict(self.values)

        delta = self.rate * dt
        wanted = directions(pressed_keys)
        for axis in AXES:
            value = self.values[axis]
            direction = wanted[axis]
            if direction != 0:
                value = _clip(value + direction * delta)
            elif axis in SPRING_AXES:
                # повернення до нуля тим самим темпом, без перестрибування
                value = 0.0 if abs(value) <= delta else value - delta * (1 if value > 0 else -1)
            # throttle без напрямку — утримується як є
            self.values[axis] = value
        return dict(self.values)
