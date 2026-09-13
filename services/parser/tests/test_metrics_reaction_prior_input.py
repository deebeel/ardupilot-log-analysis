"""§7.10 TEST-PLAN — подія на вже відхиленому стіку не вважається реакцією."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import DT
from parser.metrics import reaction_latency_ms
from test_metrics_reaction import attitude_with_spikes


def test_event_while_stick_already_deflected_is_not_measured_as_reaction() -> None:
    # Arrange
    attitude = attitude_with_spikes(400, [100])
    stick = np.full(400, 0.5)

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result is None


def test_event_from_neutral_stick_is_still_measured() -> None:
    # Arrange
    attitude = attitude_with_spikes(400, [100])
    stick = np.zeros(400)
    stick[103:120] = 0.5

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result == pytest.approx(300.0)


def test_only_the_neutral_start_event_contributes_to_the_median() -> None:
    # Arrange
    attitude = attitude_with_spikes(700, [100, 500])
    stick = np.zeros(700)
    stick[107:120] = 0.5
    stick[400:600] = 0.5

    # Act
    result = reaction_latency_ms(attitude, stick, dt=DT)

    # Assert
    assert result == pytest.approx(700.0)
