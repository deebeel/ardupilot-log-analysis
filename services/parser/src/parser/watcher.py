"""Entrypoint контейнера: стежить за inbox і спавнить воркер на кожен новий лог.

Рішення (§1.2 плану):
- реагуємо на `on_closed` (rsync/scp дає частковий файл на `on_created`);
  fallback для FS без inotify-close — `on_created` + чекання стабілізації розміру 2 с;
- воркер — окремий subprocess із таймаутом; `returncode != 0` -> `<id>.error.json`
  зі stderr, щоб веб показав «парсинг впав», а не мовчав;
- ідемпотентність: якщо результат уже новіший за вхідний файл — пропускаємо.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from parser.models import write_error
from parser.worker import DEFAULT_THRESHOLDS, flight_id_from_path

#: Розширення, які взагалі розглядаємо (усе інше — `.tmp`, `.part` — ігноруємо).
LOG_SUFFIXES: frozenset[str] = frozenset({".bin", ".BIN"})

#: Скільки секунд розмір файлу має не змінюватись, щоб вважати завантаження завершеним.
STABILIZE_S: float = 2.0

#: Максимальний час одного парсингу, с.
WORKER_TIMEOUT_S: float = 120.0

log = logging.getLogger("parser.watcher")


def is_log_file(path: str | Path) -> bool:
    """Чи цікавить нас цей файл (за розширенням)."""
    return Path(path).suffix in LOG_SUFFIXES


def is_up_to_date(source: str | Path, results_dir: str | Path) -> bool:
    """Результат уже існує і новіший за вхідний файл -> парсити не треба."""
    result = Path(results_dir) / f"{flight_id_from_path(source)}.json"
    if not result.is_file():
        return False
    return result.stat().st_mtime >= Path(source).stat().st_mtime


def wait_until_stable(path: str | Path, stabilize_s: float = STABILIZE_S,
                      timeout_s: float = 300.0) -> bool:
    """Чекати, доки розмір файлу перестане рости (fallback для FS без `on_closed`)."""
    path = Path(path)
    deadline = time.monotonic() + timeout_s
    previous = -1
    while time.monotonic() < deadline:
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == previous and size > 0:
            return True
        previous = size
        time.sleep(stabilize_s)
    return False


def run_worker(
    source: str | Path,
    results_dir: str | Path,
    thresholds: str | Path = DEFAULT_THRESHOLDS,
    timeout_s: float = WORKER_TIMEOUT_S,
) -> int:
    """Запустити воркер у subprocess. Помилка/таймаут -> `<id>.error.json`."""
    flight_id = flight_id_from_path(source)
    command = [
        sys.executable, "-m", "parser.worker", str(source),
        "--results-dir", str(results_dir),
        "--thresholds", str(thresholds),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        log.error("worker timed out on %s", source)
        write_error(flight_id, f"worker timed out after {timeout_s}s", results_dir)
        return 1

    if completed.returncode != 0:
        log.error("worker failed on %s: %s", source, completed.stderr.strip())
        write_error(
            flight_id,
            completed.stderr.strip() or f"worker exited with code {completed.returncode}",
            results_dir,
        )
        return completed.returncode

    log.info("parsed %s", source)
    return 0


def handle(source: str | Path, results_dir: str | Path,
           thresholds: str | Path = DEFAULT_THRESHOLDS) -> None:
    """Повний шлях обробки одного файлу: фільтр -> стабілізація -> ідемпотентність -> воркер."""
    if not is_log_file(source):
        return
    if not wait_until_stable(source):
        log.warning("file never stabilized, skipping: %s", source)
        return
    if is_up_to_date(source, results_dir):
        log.info("up to date, skipping: %s", source)
        return
    run_worker(source, results_dir, thresholds)


class InboxHandler(FileSystemEventHandler):
    """`on_closed` — основний тригер; `on_created` — fallback зі стабілізацією розміру."""

    def __init__(self, results_dir: Path, thresholds: Path) -> None:
        self.results_dir = results_dir
        self.thresholds = thresholds

    def _dispatch(self, event) -> None:
        if event.is_directory:
            return
        handle(event.src_path, self.results_dir, self.thresholds)

    def on_closed(self, event) -> None:
        self._dispatch(event)

    def on_created(self, event) -> None:
        self._dispatch(event)

    def on_moved(self, event) -> None:
        if not event.is_directory:
            handle(event.dest_path, self.results_dir, self.thresholds)


def scan_existing(inbox: Path, results_dir: Path, thresholds: Path) -> None:
    """Стартовий прохід: підхопити файли, що вже лежать в inbox (рестарт контейнера)."""
    for entry in sorted(inbox.iterdir()):
        if entry.is_file():
            handle(entry, results_dir, thresholds)


def main(argv: list[str] | None = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cli = argparse.ArgumentParser(description="Watch inbox and parse incoming .bin logs")
    cli.add_argument("--inbox", default=os.environ.get("INBOX_DIR", "/data/inbox"))
    cli.add_argument("--results-dir", default=os.environ.get("RESULTS_DIR", "/data/results"))
    cli.add_argument("--thresholds", default=os.environ.get("THRESHOLDS", str(DEFAULT_THRESHOLDS)))
    args = cli.parse_args(argv)

    inbox = Path(args.inbox)
    results_dir = Path(args.results_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    scan_existing(inbox, results_dir, Path(args.thresholds))

    observer = Observer()
    observer.schedule(InboxHandler(results_dir, Path(args.thresholds)), str(inbox), recursive=False)
    observer.start()
    log.info("watching %s -> %s", inbox, results_dir)
    try:
        while observer.is_alive():
            observer.join(1.0)
    except KeyboardInterrupt:  # pragma: no cover - сигнал
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
