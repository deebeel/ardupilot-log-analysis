"""Чисті функції метрик якості пілотування (п.3 тікета, §1.4 плану).

Жодного I/O, жодних порогів вердикту — тільки детерміновані числа над numpy-серіями.
Усі серії вважаються вже нормалізованими в [-1, +1] і ресемпленими на рівномірну сітку `dt`.
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import numpy.typing as npt

#: Псевдоніми для numpy-серій, щоб сигнатури лишались читабельними.
FloatArray: TypeAlias = npt.NDArray[np.float64]
BoolArray: TypeAlias = npt.NDArray[np.bool_]
IntArray: TypeAlias = npt.NDArray[np.intp]

#: Все, що за модулем <= DEADBAND, вважається нейтраллю (межа включно).
DEADBAND: float = 0.02

#: Вікно для метрики осциляцій, с.
OSCILLATION_WINDOW_S: float = 2.0

#: Мінімальна кількість змін знаку у вікні, щоб вважати його осциляцією.
OSCILLATION_MIN_SIGN_CHANGES: int = 3

#: Скільки чекати реакції оператора на attitude-подію, с.
REACTION_WINDOW_S: float = 3.0

#: Поріг attitude-події (відхилення від повільного baseline), градуси.
ATTITUDE_EVENT_THRESHOLD_DEG: float = 10.0

#: Ширина baseline-вікна для детрендингу attitude, с.
ATTITUDE_BASELINE_S: float = 5.0


def outside_deadband(values: FloatArray, deadband: float = DEADBAND) -> BoolArray:
    """Булева маска семплів поза deadband (рівно на межі — всередині)."""
    return np.abs(np.asarray(values, dtype=np.float64)) > deadband


def corrections_per_min(
    values: FloatArray, duration_s: float, deadband: float = DEADBAND
) -> float:
    """Кількість виходів за deadband на хвилину.

    Стан «до початку серії» вважається нейтральним, тож серія, що одразу починається
    поза deadband, дає одну корекцію.
    """
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0 or duration_s <= 0:
        return 0.0
    out = outside_deadband(values, deadband)
    previous = np.concatenate(([False], out[:-1]))
    crossings = int(np.count_nonzero(out & ~previous))
    return crossings / (duration_s / 60.0)


def mean_amplitude(values: FloatArray, deadband: float = DEADBAND) -> float:
    """Середнє |значення| по семплах поза deadband (семпли в deadband не враховуються)."""
    values = np.asarray(values, dtype=np.float64)
    active = np.abs(values[outside_deadband(values, deadband)])
    if active.size == 0:
        return 0.0
    return float(np.mean(active))


def _smooth3(values: FloatArray) -> FloatArray:
    """Ковзне середнє по 3 семплах (`valid`); для коротких серій — без згладжування."""
    if values.size < 3:
        return values
    return np.convolve(values, np.full(3, 1.0 / 3.0), mode="valid")


def mean_jerk(values: FloatArray, dt: float) -> float:
    """Середня |похідна| згладженої серії (одиниць нормованого ходу стіка за секунду)."""
    values = np.asarray(values, dtype=np.float64)
    if values.size < 2 or dt <= 0:
        return 0.0
    smoothed = _smooth3(values)
    if smoothed.size < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff(smoothed))) / dt)


def oscillation_time_pct(
    values: FloatArray,
    dt: float,
    window_s: float = OSCILLATION_WINDOW_S,
    min_sign_changes: int = OSCILLATION_MIN_SIGN_CHANGES,
    deadband: float = DEADBAND,
) -> float:
    """Частка часу [0..1], проведена у вікнах з >= `min_sign_changes` змінами знаку."""
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0 or dt <= 0:
        return 0.0
    window = int(round(window_s / dt))
    if window < 2 or values.size < window:
        return 0.0

    signs = np.sign(values)
    signs[~outside_deadband(values, deadband)] = 0.0

    # Зміна знаку між двома сусідніми НЕнульовими знаками; нулі (deadband) прозорі.
    nonzero_idx = np.flatnonzero(signs)
    changes = np.zeros(values.size, dtype=np.float64)
    if nonzero_idx.size >= 2:
        flipped = signs[nonzero_idx[1:]] != signs[nonzero_idx[:-1]]
        changes[nonzero_idx[1:]] = flipped.astype(float)

    cumulative = np.concatenate(([0.0], np.cumsum(changes)))
    window_changes = cumulative[window:] - cumulative[:-window]
    return float(np.count_nonzero(window_changes >= min_sign_changes) / window_changes.size)


def _rising_edges(mask: BoolArray) -> IntArray:
    """Індекси, де маска переходить False -> True (перший семпл теж може бути подією)."""
    previous = np.concatenate(([False], mask[:-1]))
    return np.flatnonzero(mask & ~previous)


def attitude_events(
    attitude_deg: FloatArray,
    dt: float,
    threshold_deg: float = ATTITUDE_EVENT_THRESHOLD_DEG,
    baseline_s: float = ATTITUDE_BASELINE_S,
) -> IntArray:
    """Індекси подій «attitude-помилка перевищила поріг» (детрендинг повільним baseline)."""
    attitude_deg = np.asarray(attitude_deg, dtype=np.float64)
    if attitude_deg.size == 0 or dt <= 0:
        return np.empty(0, dtype=int)
    window = max(1, int(round(baseline_s / dt)))
    kernel = np.full(window, 1.0 / window)
    padded = np.pad(attitude_deg, (window // 2, window - 1 - window // 2), mode="edge")
    baseline = np.convolve(padded, kernel, mode="valid")[: attitude_deg.size]
    return _rising_edges(np.abs(attitude_deg - baseline) > threshold_deg)


def reaction_latencies_ms(
    attitude_deg: FloatArray,
    stick: FloatArray,
    dt: float,
    threshold_deg: float = ATTITUDE_EVENT_THRESHOLD_DEG,
    window_s: float = REACTION_WINDOW_S,
    deadband: float = DEADBAND,
    baseline_s: float = ATTITUDE_BASELINE_S,
) -> list[float]:
    """Затримки реакції по кожній attitude-події, мс.

    Відкидаються: події без реакції протягом `window_s` і події, на момент яких стік
    **уже** був поза deadband — там немає чого міряти, це не реакція, а продовження руху
    (інакше метрика виродилась би в 0 мс на будь-якому маневреному польоті).
    """
    stick = np.asarray(stick, dtype=np.float64)
    events = attitude_events(attitude_deg, dt, threshold_deg, baseline_s)
    if events.size == 0 or stick.size == 0:
        return []

    moved = outside_deadband(stick, deadband)
    horizon = max(1, int(round(window_s / dt)))
    latencies: list[float] = []
    for event in events:
        if event > 0 and moved[event - 1]:
            continue
        end = min(stick.size, event + horizon + 1)
        offsets = np.flatnonzero(moved[event:end])
        if offsets.size > 0:
            latencies.append(float(offsets[0]) * dt * 1000.0)
    return latencies


def reaction_latency_ms(
    attitude_deg: FloatArray,
    stick: FloatArray,
    dt: float,
    threshold_deg: float = ATTITUDE_EVENT_THRESHOLD_DEG,
    window_s: float = REACTION_WINDOW_S,
    deadband: float = DEADBAND,
    baseline_s: float = ATTITUDE_BASELINE_S,
) -> float | None:
    """Медіанна затримка реакції оператора, мс; `None` якщо подій або реакцій нема."""
    latencies = reaction_latencies_ms(
        attitude_deg, stick, dt, threshold_deg, window_s, deadband, baseline_s
    )
    if not latencies:
        return None
    return float(np.median(latencies))


def amplitude_histogram(
    values: FloatArray, bins: int = 20, deadband: float = DEADBAND
) -> tuple[list[float], list[int]]:
    """Гістограма |відхилень| поза deadband: (`bin_edges`, `counts`)."""
    values = np.asarray(values, dtype=np.float64)
    active = np.abs(values[outside_deadband(values, deadband)])
    counts, edges = np.histogram(active, bins=bins, range=(0.0, 1.0))
    return [float(e) for e in edges], [int(c) for c in counts]
