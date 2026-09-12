"""Спільні фікстури й генератори синтетичних серій з аналітично відомою відповіддю."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

#: Крок спільної сітки, що його використовує reader (10 Гц).
DT = 0.1

#: Реальний лог для smoke-тесту (лежить в assets/ кореня worktree).
REAL_LOG = Path(__file__).resolve().parents[3] / "assets" / "flight-01_2026-09-11.bin"

#: Конфіг дефолтних порогів сервісу.
THRESHOLDS = Path(__file__).resolve().parents[1] / "thresholds.yaml"


def sine(frequency_hz: float, duration_s: float, amplitude: float = 1.0, dt: float = DT):
    """Синусоїда відомої частоти на рівномірній сітці (початок — у нулі, зростаюча)."""
    t = np.arange(0.0, duration_s, dt)
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * t)


def ramp(slope_per_sample: float, count: int):
    """Лінійний ramp зі сталим приростом на семпл."""
    return slope_per_sample * np.arange(count, dtype=float)


def grow_file_in_background(path: Path, chunks: int, interval_s: float):
    """Дописує файл у фоні — імітація rsync, що ще не закінчив передачу."""
    import threading

    def _grow():
        import time as _time

        for _ in range(chunks):
            with path.open("ab") as handle:
                handle.write(b"x" * 1024)
            _time.sleep(interval_s)

    thread = threading.Thread(target=_grow, daemon=True)
    thread.start()
    return thread


@pytest.fixture(scope="session")
def real_log_path() -> Path:
    """Шлях до реального демо-логу; тест пропускається, якщо файлу нема (git-lfs)."""
    if not REAL_LOG.is_file() or REAL_LOG.stat().st_size < 1_000_000:
        pytest.skip(f"real log unavailable: {REAL_LOG}")
    return REAL_LOG


@pytest.fixture(scope="session")
def real_result(real_log_path):
    """Результат аналізу реального логу — рахується один раз на сесію (парсинг довгий)."""
    from parser.worker import analyze

    return analyze(real_log_path, THRESHOLDS)
