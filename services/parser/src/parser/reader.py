"""DataFlash (`.bin`) -> нормалізовані ресемплені серії (§1.3 плану).

Відповідальність: витягти RCIN/ATT/MODE/PARM, нормалізувати стіки в [-1, +1] за
RC*_MIN/TRIM/MAX, привести все на спільну сітку 10 Гц і позначити ручні фази.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

#: Частота спільної сітки ресемплінгу, Гц.
RESAMPLE_HZ: float = 10.0

#: Крок спільної сітки, с.
DT: float = 1.0 / RESAMPLE_HZ

#: Фолбек-калібрування RC, якщо в логу немає відповідних PARM.
DEFAULT_RC_MIN: float = 1000.0
DEFAULT_RC_TRIM: float = 1500.0
DEFAULT_RC_MAX: float = 2000.0

#: Осі керування -> номер RC-каналу (стандартний ArduPlane mapping).
AXIS_CHANNELS: dict[str, int] = {"roll": 1, "pitch": 2, "yaw": 4}

#: Номери режимів ArduPlane -> імена (не залежимо від внутрішніх таблиць pymavlink).
PLANE_MODE_NAMES: dict[int, str] = {
    0: "MANUAL",
    1: "CIRCLE",
    2: "STABILIZE",
    3: "TRAINING",
    4: "ACRO",
    5: "FBWA",
    6: "FBWB",
    7: "CRUISE",
    8: "AUTOTUNE",
    9: "AUTOROTATE",
    10: "AUTO",
    11: "RTL",
    12: "LOITER",
    13: "TAKEOFF",
    14: "AVOID_ADSB",
    15: "GUIDED",
    17: "QSTABILIZE",
    18: "QHOVER",
    19: "QLOITER",
    20: "QLAND",
    21: "QRTL",
    22: "QAUTOTUNE",
    23: "QACRO",
    24: "THERMAL",
    25: "LOITER_ALT_QLAND",
}

#: Режими, в яких пілотує людина — лише вони аналізуються.
MANUAL_MODES: frozenset[str] = frozenset({"MANUAL", "STABILIZE", "FBWA", "FBWB"})


class LogReadError(RuntimeError):
    """Лог не читається / не містить потрібних записів."""


@dataclass
class RcCalibration:
    """Калібрування одного RC-каналу."""

    min: float = DEFAULT_RC_MIN
    trim: float = DEFAULT_RC_TRIM
    max: float = DEFAULT_RC_MAX


@dataclass
class FlightData:
    """Нормалізовані серії на спільній сітці + фази режимів."""

    t: np.ndarray
    sticks: dict[str, np.ndarray]
    att_roll: np.ndarray
    att_pitch: np.ndarray
    manual_mask: np.ndarray
    phases: list[dict] = field(default_factory=list)
    dt: float = DT

    @property
    def duration_s(self) -> float:
        if self.t.size == 0:
            return 0.0
        return float(self.t[-1] - self.t[0])

    @property
    def analyzed_duration_s(self) -> float:
        return float(np.count_nonzero(self.manual_mask) * self.dt)


def mode_name(number: int) -> str:
    """Ім'я режиму за номером; невідомий -> `MODE_<n>` (і він не ручний)."""
    return PLANE_MODE_NAMES.get(int(number), f"MODE_{int(number)}")


def normalize_channel(pwm: np.ndarray | float, calibration: RcCalibration) -> np.ndarray:
    """PWM -> [-1, +1], окремими half-range нижче й вище trim, з кліпом."""
    pwm = np.asarray(pwm, dtype=float)
    below = calibration.trim - calibration.min
    above = calibration.max - calibration.trim
    delta = pwm - calibration.trim
    # Вироджений half-range (нульова ширина) не повинен давати ділення на нуль.
    low = np.divide(delta, below, out=np.zeros_like(delta), where=below > 0)
    high = np.divide(delta, above, out=np.zeros_like(delta), where=above > 0)
    return np.clip(np.where(delta < 0, low, high), -1.0, 1.0)


def rc_calibrations(params: dict[str, float]) -> dict[str, RcCalibration]:
    """Калібрування по осях з PARM-словника, з фолбеком 1000/1500/2000."""
    result: dict[str, RcCalibration] = {}
    for axis, channel in AXIS_CHANNELS.items():
        result[axis] = RcCalibration(
            min=float(params.get(f"RC{channel}_MIN", DEFAULT_RC_MIN)),
            trim=float(params.get(f"RC{channel}_TRIM", DEFAULT_RC_TRIM)),
            max=float(params.get(f"RC{channel}_MAX", DEFAULT_RC_MAX)),
        )
    return result


def build_phases(
    mode_changes: list[tuple[float, str]], start_s: float, end_s: float
) -> list[dict]:
    """Список фаз з подій MODE; остання фаза закривається кінцем логу."""
    if not mode_changes:
        return []
    phases: list[dict] = []
    for index, (timestamp, name) in enumerate(mode_changes):
        begin = max(timestamp, start_s)
        finish = mode_changes[index + 1][0] if index + 1 < len(mode_changes) else end_s
        if finish <= begin:
            continue
        phases.append(
            {
                "mode": name,
                "start_s": round(begin - start_s, 3),
                "end_s": round(finish - start_s, 3),
                "duration_s": round(finish - begin, 3),
                "manual": name in MANUAL_MODES,
            }
        )
    return phases


def manual_mask_from_phases(t: np.ndarray, phases: list[dict]) -> np.ndarray:
    """Булева маска семплів, що потрапляють у ручні фази."""
    mask = np.zeros(t.size, dtype=bool)
    for phase in phases:
        if phase["manual"]:
            mask |= (t >= phase["start_s"]) & (t < phase["end_s"])
    return mask


def resample(times: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Лінійна інтерполяція на спільну сітку; порожній вхід -> нулі."""
    if times.size == 0:
        return np.zeros(grid.size, dtype=float)
    if times.size == 1:
        return np.full(grid.size, float(values[0]))
    return np.interp(grid, times, values)


def _raw_records(path: str | Path) -> dict:
    """Сирий прохід по логу: PARM, RCIN, ATT, MODE."""
    from pymavlink import mavutil  # локальний імпорт: важкий і потрібен лише тут

    connection = mavutil.mavlink_connection(str(path))
    params: dict[str, float] = {}
    rc_t: list[float] = []
    rc_v: dict[int, list[float]] = {c: [] for c in AXIS_CHANNELS.values()}
    att_t: list[float] = []
    att_roll: list[float] = []
    att_pitch: list[float] = []
    modes: list[tuple[float, str]] = []

    while True:
        message = connection.recv_match(type=["PARM", "RCIN", "ATT", "MODE"])
        if message is None:
            break
        kind = message.get_type()
        timestamp = float(getattr(message, "TimeUS", 0)) / 1e6
        if kind == "PARM":
            params[str(message.Name)] = float(message.Value)
        elif kind == "RCIN":
            rc_t.append(timestamp)
            for channel in rc_v:
                rc_v[channel].append(float(getattr(message, f"C{channel}", 1500.0)))
        elif kind == "ATT":
            att_t.append(timestamp)
            att_roll.append(float(message.Roll))
            att_pitch.append(float(message.Pitch))
        elif kind == "MODE":
            number = getattr(message, "ModeNum", getattr(message, "Mode", -1))
            modes.append((timestamp, mode_name(number)))

    return {
        "params": params,
        "rc_t": np.asarray(rc_t, dtype=float),
        "rc_v": {c: np.asarray(v, dtype=float) for c, v in rc_v.items()},
        "att_t": np.asarray(att_t, dtype=float),
        "att_roll": np.asarray(att_roll, dtype=float),
        "att_pitch": np.asarray(att_pitch, dtype=float),
        "modes": modes,
    }


def read_flight(path: str | Path) -> FlightData:
    """Прочитати `.bin` і повернути нормалізовані ресемплені серії."""
    path = Path(path)
    if not path.is_file():
        raise LogReadError(f"file not found: {path}")
    raw = _raw_records(path)

    if raw["rc_t"].size == 0 or raw["att_t"].size == 0:
        raise LogReadError(
            f"log has no usable RCIN/ATT records "
            f"(RCIN={raw['rc_t'].size}, ATT={raw['att_t'].size})"
        )

    start = float(min(raw["rc_t"][0], raw["att_t"][0]))
    end = float(max(raw["rc_t"][-1], raw["att_t"][-1]))
    if end <= start:
        raise LogReadError("log time span is empty")

    grid = np.arange(0.0, end - start, DT)
    calibrations = rc_calibrations(raw["params"])
    sticks = {
        axis: normalize_channel(
            resample(raw["rc_t"] - start, raw["rc_v"][channel], grid),
            calibrations[axis],
        )
        for axis, channel in AXIS_CHANNELS.items()
    }
    att_roll = resample(raw["att_t"] - start, raw["att_roll"], grid)
    att_pitch = resample(raw["att_t"] - start, raw["att_pitch"], grid)
    phases = build_phases(raw["modes"], start, end)

    return FlightData(
        t=grid,
        sticks=sticks,
        att_roll=att_roll,
        att_pitch=att_pitch,
        manual_mask=manual_mask_from_phases(grid, phases),
        phases=phases,
    )
