"""Entrypoint воркера: один вхідний лог -> один JSON результату.

Запускається watcher-ом як окремий subprocess (`python -m parser.worker <file>`), щоб
падіння `DFReader` на одному файлі не валило прийом інших.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

from parser import metrics as M
from parser.models import FlightResult, Metrics, Phase, downsample, load_thresholds, write_json_atomic
from parser.reader import FlightData, read_flight

#: Дефолтні шляхи в контейнері (перевизначаються аргументами CLI).
DEFAULT_RESULTS_DIR: Path = Path("/data/results")
DEFAULT_THRESHOLDS: Path = Path(__file__).resolve().parents[2] / "thresholds.yaml"

_ID_SAFE: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_-]+")


def flight_id_from_path(path: str | Path) -> str:
    """`flight-01_2026-09-11.bin` -> `flight-01_2026-09-11` (безпечно для шляхів і URL)."""
    return _ID_SAFE.sub("_", Path(path).stem)


def contiguous_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    """Пари (start, stop) для неперервних блоків True у масці."""
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    return [(int(a), int(b)) for a, b in zip(starts, stops) if b > a]


def _weighted(values: list[float], weights: list[float]) -> float:
    total = float(sum(weights))
    if total <= 0:
        return 0.0
    return float(sum(v * w for v, w in zip(values, weights)) / total)


def compute_metrics(flight: FlightData) -> Metrics:
    """5 метрик §1.4, пораховані лише по ручних фазах, посегментно й зважено."""
    dt = flight.dt
    segments = contiguous_segments(flight.manual_mask)
    weights = [(stop - start) * dt for start, stop in segments]

    corrections: dict[str, float] = {}
    amplitude: dict[str, float] = {}
    jerk: dict[str, float] = {}
    oscillation: dict[str, float] = {}

    for axis, series in flight.sticks.items():
        pieces = [series[start:stop] for start, stop in segments]
        joined = np.concatenate(pieces) if pieces else np.empty(0)
        corrections[axis] = _weighted(
            [M.corrections_per_min(p, w) for p, w in zip(pieces, weights)], weights
        )
        amplitude[axis] = M.mean_amplitude(joined)
        jerk[axis] = _weighted([M.mean_jerk(p, dt) for p in pieces], weights)
        oscillation[axis] = _weighted(
            [M.oscillation_time_pct(p, dt) for p in pieces], weights
        )

    latencies: list[float] = []
    attitude_by_axis = {"roll": flight.att_roll, "pitch": flight.att_pitch}
    for start, stop in segments:
        for axis, attitude in attitude_by_axis.items():
            latencies.extend(
                M.reaction_latencies_ms(
                    attitude[start:stop], flight.sticks[axis][start:stop], dt
                )
            )
    latency = float(np.median(latencies)) if latencies else None

    return Metrics(
        corrections_per_min={k: round(v, 4) for k, v in corrections.items()},
        mean_amplitude={k: round(v, 4) for k, v in amplitude.items()},
        mean_jerk={k: round(v, 4) for k, v in jerk.items()},
        oscillation_time_pct={k: round(v, 4) for k, v in oscillation.items()},
        reaction_latency_ms=round(latency, 1) if latency is not None else None,
    )


def analyze(path: str | Path, thresholds_path: str | Path = DEFAULT_THRESHOLDS) -> FlightResult:
    """Повний конвеєр: читання -> нормалізація -> метрики -> контракт JSON."""
    flight = read_flight(path)
    computed = compute_metrics(flight)

    segments = contiguous_segments(flight.manual_mask)
    amplitude_histograms: dict[str, dict[str, list[float] | list[int]]] = {}
    for axis, series in flight.sticks.items():
        manual_series = np.concatenate(
            [series[a:b] for a, b in segments] or [np.empty(0)]
        )
        edges, counts = M.amplitude_histogram(manual_series)
        amplitude_histograms[axis] = {"bins": edges, "counts": counts}

    warnings: list[str] = []
    if not flight.phases:
        warnings.append("log has no MODE records; manual-phase mask is empty")
    if flight.analyzed_duration_s <= 0:
        warnings.append("no manual-mode phases found; metrics are zero/null")

    crashed = flight.stat_crash_any or M.detect_crash_heuristic(
        flight.rel_alt, flight.att_roll, flight.att_pitch, flight.dt
    )

    return FlightResult(
        flight_id=flight_id_from_path(path),
        duration_s=round(flight.duration_s, 3),
        analyzed_duration_s=round(flight.analyzed_duration_s, 3),
        source_file=Path(path).name,
        phases=[Phase(**phase) for phase in flight.phases],
        metrics=computed,
        default_thresholds=load_thresholds(thresholds_path),
        series={
            "t": downsample(flight.t),
            "roll": downsample(flight.sticks["roll"]),
            "pitch": downsample(flight.sticks["pitch"]),
            "att_roll": downsample(flight.att_roll),
            "att_pitch": downsample(flight.att_pitch),
        },
        amplitude_histogram=amplitude_histograms,
        warnings=warnings,
        crashed=crashed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse one ArduPlane .bin log into a result JSON")
    parser.add_argument("log", help="path to the DataFlash .bin log")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    args = parser.parse_args(argv)

    result = analyze(args.log, args.thresholds)
    destination = Path(args.results_dir) / f"{result.flight_id}.json"
    write_json_atomic(result.to_dict(), destination)
    print(destination, file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
