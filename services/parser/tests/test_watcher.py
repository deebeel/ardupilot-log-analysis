"""§10 TEST-PLAN — watcher: фільтр файлів, стабілізація, ідемпотентність, помилки воркера."""

from __future__ import annotations

import json
import os
import time

import pytest

from conftest import THRESHOLDS, grow_file_in_background
from parser.watcher import handle, is_log_file, is_up_to_date, run_worker, wait_until_stable


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("flight-01.bin", True),
        ("flight-01.BIN", True),
        ("flight-01.bin.tmp", False),
        ("flight-01.part", False),
        ("flight-01.tlog", False),
        ("notes.txt", False),
    ],
)
def test_only_dataflash_logs_are_accepted_for_parsing(name, expected):
    # Arrange / параметризовано вище

    # Act
    result = is_log_file(name)

    # Assert
    assert result is expected


def test_result_newer_than_source_is_considered_up_to_date(tmp_path):
    # Arrange
    source = tmp_path / "flight-01.bin"
    source.write_bytes(b"data")
    result = tmp_path / "flight-01.json"
    result.write_text("{}")
    os.utime(result, (time.time() + 100, time.time() + 100))

    # Act
    up_to_date = is_up_to_date(source, tmp_path)

    # Assert
    assert up_to_date is True


def test_result_older_than_source_is_not_up_to_date(tmp_path):
    # Arrange
    result = tmp_path / "flight-01.json"
    result.write_text("{}")
    source = tmp_path / "flight-01.bin"
    source.write_bytes(b"data")
    os.utime(source, (time.time() + 100, time.time() + 100))

    # Act
    up_to_date = is_up_to_date(source, tmp_path)

    # Assert
    assert up_to_date is False


def test_absent_result_is_not_up_to_date(tmp_path):
    # Arrange
    source = tmp_path / "flight-01.bin"
    source.write_bytes(b"data")

    # Act
    up_to_date = is_up_to_date(source, tmp_path)

    # Assert
    assert up_to_date is False


def test_static_file_is_reported_as_stable(tmp_path):
    # Arrange
    path = tmp_path / "flight-01.bin"
    path.write_bytes(b"complete payload")

    # Act
    stable = wait_until_stable(path, stabilize_s=0.05, timeout_s=2.0)

    # Assert
    assert stable is True


def test_missing_file_is_not_reported_as_stable(tmp_path):
    # Arrange
    path = tmp_path / "absent.bin"

    # Act
    stable = wait_until_stable(path, stabilize_s=0.05, timeout_s=1.0)

    # Assert
    assert stable is False


def test_file_still_being_appended_is_not_reported_as_stable(tmp_path):
    # Arrange
    path = tmp_path / "flight-01.bin"
    path.write_bytes(b"start")
    grow_file_in_background(path, chunks=40, interval_s=0.05)

    # Act
    stable = wait_until_stable(path, stabilize_s=0.1, timeout_s=1.0)

    # Assert
    assert stable is False


def test_corrupt_log_produces_an_error_result(tmp_path):
    # Arrange
    source = tmp_path / "flight-broken.bin"
    source.write_bytes(b"this is definitely not a dataflash log")

    # Act
    run_worker(source, tmp_path, THRESHOLDS, timeout_s=120.0)

    # Assert
    assert (tmp_path / "flight-broken.error.json").is_file()


def test_error_result_contains_the_worker_stderr(tmp_path):
    # Arrange
    source = tmp_path / "flight-broken.bin"
    source.write_bytes(b"this is definitely not a dataflash log")

    # Act
    run_worker(source, tmp_path, THRESHOLDS, timeout_s=120.0)

    # Assert
    assert json.loads((tmp_path / "flight-broken.error.json").read_text())["error"] != ""


def test_worker_timeout_produces_an_error_result(tmp_path):
    # Arrange
    source = tmp_path / "flight-slow.bin"
    source.write_bytes(b"not a real log")

    # Act
    run_worker(source, tmp_path, THRESHOLDS, timeout_s=0.001)

    # Assert
    assert "timed out" in json.loads((tmp_path / "flight-slow.error.json").read_text())["error"]


def test_worker_failure_returns_nonzero_exit_code(tmp_path):
    # Arrange
    source = tmp_path / "flight-broken.bin"
    source.write_bytes(b"nope")

    # Act
    code = run_worker(source, tmp_path, THRESHOLDS, timeout_s=120.0)

    # Assert
    assert code != 0


def test_up_to_date_file_is_skipped_without_spawning_the_worker(tmp_path):
    # Arrange
    source = tmp_path / "flight-01.bin"
    source.write_bytes(b"not a real log")
    marker = tmp_path / "flight-01.json"
    marker.write_text('{"flight_id": "flight-01"}')
    os.utime(marker, (time.time() + 100, time.time() + 100))

    # Act
    handle(source, tmp_path, THRESHOLDS)

    # Assert
    assert not (tmp_path / "flight-01.error.json").exists()


def test_non_log_file_is_ignored_by_the_handler(tmp_path):
    # Arrange
    source = tmp_path / "partial.bin.tmp"
    source.write_bytes(b"half a log")

    # Act
    handle(source, tmp_path, THRESHOLDS)

    # Assert
    assert list(tmp_path.glob("*.json")) == []


def test_failed_parse_does_not_block_the_next_file(tmp_path):
    # Arrange
    broken = tmp_path / "flight-bad.bin"
    broken.write_bytes(b"garbage")
    second = tmp_path / "flight-other.bin"
    second.write_bytes(b"garbage too")
    run_worker(broken, tmp_path, THRESHOLDS, timeout_s=120.0)

    # Act
    run_worker(second, tmp_path, THRESHOLDS, timeout_s=120.0)

    # Assert
    assert (tmp_path / "flight-other.error.json").is_file()
