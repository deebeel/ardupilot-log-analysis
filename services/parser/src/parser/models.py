"""Dataclass-и вихідного контракту та атомарний запис JSON (§1.5 плану)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

#: Максимум точок на канал у серіях для графіків.
MAX_SERIES_POINTS: int = 2000

#: Ключі, які сервер НЕ віддає (вердикт рахує клієнт).
FORBIDDEN_KEYS: tuple[str, ...] = ("verdict", "reasons")


@dataclass(frozen=True)
class Phase:
    """Відрізок польоту в одному режимі."""

    mode: str
    start_s: float
    end_s: float
    duration_s: float
    manual: bool


@dataclass(frozen=True)
class Metrics:
    """Сирі детерміновані метрики (без порогів і без вердикту)."""

    corrections_per_min: dict[str, float]
    mean_amplitude: dict[str, float]
    mean_jerk: dict[str, float]
    oscillation_time_pct: dict[str, float]
    reaction_latency_ms: float | None


@dataclass(frozen=True)
class FlightResult:
    """Повний вихідний JSON для одного польоту."""

    flight_id: str
    duration_s: float
    phases: list[Phase]
    metrics: Metrics
    default_thresholds: dict[str, Any]
    series: dict[str, list[float]]
    amplitude_histogram: dict[str, Any]
    analyzed_duration_s: float = 0.0
    source_file: str = ""
    schema_version: int = 1
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def downsample(values: np.ndarray, limit: int = MAX_SERIES_POINTS) -> list[float]:
    """Рівномірне прорідження до <= `limit` точок; коротші серії не змінюються."""
    values = np.asarray(values, dtype=float)
    if values.size <= limit:
        return [float(v) for v in values]
    idx = np.linspace(0, values.size - 1, limit).astype(int)
    return [float(v) for v in values[idx]]


def load_thresholds(path: str | Path) -> dict[str, Any]:
    """Читає `thresholds.yaml`; відсутній файл -> порожній конфіг (не падаємо)."""
    path = Path(path)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json_atomic(payload: dict[str, Any], destination: str | Path) -> Path:
    """Пише JSON атомарно: `*.json.tmp` -> `os.rename` (веб ніколи не бачить півфайлу)."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    os.rename(tmp, destination)
    return destination


def write_error(flight_id: str, message: str, results_dir: str | Path) -> Path:
    """Пише `<id>.error.json`, щоб веб показав «парсинг впав», а не мовчав."""
    return write_json_atomic(
        {"flight_id": flight_id, "error": message},
        Path(results_dir) / f"{flight_id}.error.json",
    )
