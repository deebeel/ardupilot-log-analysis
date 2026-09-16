"""Тести чистої логіки осей. Сценарії — див. TEST-PLAN.md (нумерація збігається)."""

from __future__ import annotations

import pytest

from keyboard_adapter.axes import RANGE, AxisState, directions
from helpers import advance, steps_to_zero

RATE = 2000.0  # дефолт: 0 → 1000 за 0.5 с


# 1
def test_idle_state_without_keys_stays_at_zero() -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [], n=10)

    # Assert
    assert values == {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "throttle": 0.0}


# 2
def test_holding_key_exactly_to_full_range_reaches_limit() -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, ["d"], n=10)  # 10*0.05*2000 = 1000

    # Assert
    assert values["roll"] == RANGE


# 3
@pytest.mark.parametrize(
    "key, axis, expected",
    [("d", "roll", RANGE), ("a", "roll", -RANGE), ("w", "pitch", RANGE), ("s", "pitch", -RANGE)],
)
def test_holding_key_past_full_range_is_clipped(key: str, axis: str, expected: float) -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [key], n=40)  # удвічі довше, ніж треба

    # Assert
    assert values[axis] == expected


# 4
def test_release_from_max_decreases_by_one_rate_step() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=10)

    # Act
    values = state.step(0.05, [])

    # Assert
    assert values["roll"] == pytest.approx(RANGE - RATE * 0.05)


# 4
def test_release_from_max_returns_to_zero_in_expected_step_count() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=10)

    # Act
    steps = steps_to_zero(state, 0.05, "roll")

    # Assert
    assert steps == 10


# 5, 6
@pytest.mark.parametrize("key, expected_sign_value", [("d", RANGE), ("a", -RANGE)])
def test_spring_return_with_huge_dt_lands_exactly_on_zero(key: str, expected_sign_value: float) -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.5, [key], n=1)  # roll = expected_sign_value

    # Act
    values = state.step(10.0, [])  # перестрибнуло б далеко за нуль

    # Assert
    assert values["roll"] == 0.0


# 7
def test_opposite_keys_held_together_spring_return_toward_zero() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=10)

    # Act
    values = state.step(0.05, ["a", "d"])

    # Assert
    assert values["roll"] == pytest.approx(RANGE - RATE * 0.05)


# 8
def test_opposite_keys_at_zero_keep_axis_at_zero() -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, ["a", "d"], n=5)

    # Assert
    assert values["roll"] == 0.0


# 9
@pytest.mark.parametrize("keys", [[], ["d"]])
def test_zero_dt_leaves_value_unchanged(keys: list[str]) -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=4)  # roll = 400
    before = state.values["roll"]

    # Act
    values = state.step(0.0, keys)

    # Assert
    assert values["roll"] == before


# 10
@pytest.mark.parametrize("dt", [-0.05, -10.0])
def test_negative_dt_leaves_value_unchanged(dt: float) -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=4)
    before = state.values["roll"]

    # Act
    values = state.step(dt, ["d"])

    # Assert
    assert values["roll"] == before


# 11
def test_absurdly_large_dt_while_pressed_is_clipped_to_range() -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = state.step(10.0, ["d"])

    # Assert
    assert values["roll"] == RANGE


# 12
def test_direction_change_without_release_crosses_zero() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=10)  # roll = +1000

    # Act
    values = advance(state, 0.05, ["a"], n=11)  # 11*100 = 1100 вниз

    # Assert
    assert values["roll"] == pytest.approx(-100.0)


# 13
def test_press_release_press_resumes_from_current_value() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["d"], n=6)  # 600
    advance(state, 0.05, [], n=2)  # 400

    # Act
    values = state.step(0.05, ["d"])

    # Assert
    assert values["roll"] == pytest.approx(500.0)


# 14, 15
@pytest.mark.parametrize("key, expected", [("up", 500.0), ("down", -500.0)])
def test_throttle_keys_move_throttle_in_expected_direction(key: str, expected: float) -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [key], n=5)

    # Assert
    assert values["throttle"] == pytest.approx(expected)


# 16
def test_throttle_holds_value_after_release() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["up"], n=5)  # 500

    # Act
    values = advance(state, 0.05, [], n=20)

    # Assert
    assert values["throttle"] == pytest.approx(500.0)


# 17
@pytest.mark.parametrize("key, expected", [("up", RANGE), ("down", -RANGE)])
def test_throttle_is_clipped_to_range(key: str, expected: float) -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [key], n=40)

    # Assert
    assert values["throttle"] == expected


# 18
def test_throttle_with_both_keys_held_holds_value() -> None:
    # Arrange
    state = AxisState(rate=RATE)
    advance(state, 0.05, ["up"], n=5)  # 500

    # Act
    values = advance(state, 0.05, ["up", "down"], n=10)

    # Assert
    assert values["throttle"] == pytest.approx(500.0)


# 19
@pytest.mark.parametrize(
    "key, axis",
    [
        ("w", "pitch"),
        ("s", "pitch"),
        ("a", "roll"),
        ("d", "roll"),
        ("q", "yaw"),
        ("e", "yaw"),
        ("up", "throttle"),
        ("down", "throttle"),
    ],
)
def test_key_moves_only_its_own_axis(key: str, axis: str) -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [key], n=3)

    # Assert
    assert {name for name, value in values.items() if value != 0.0} == {axis}


# 20
def test_unknown_key_moves_nothing() -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, ["z"], n=5)

    # Assert
    assert set(values.values()) == {0.0}


# 21
@pytest.mark.parametrize("key", ["D", "d"])
def test_key_case_is_ignored(key: str) -> None:
    # Arrange
    state = AxisState(rate=RATE)

    # Act
    values = advance(state, 0.05, [key], n=2)

    # Assert
    assert values["roll"] == pytest.approx(200.0)


# 7 (рівень directions)
def test_directions_cancels_opposite_keys() -> None:
    # Arrange
    keys = ["a", "d"]

    # Act
    result = directions(keys)

    # Assert
    assert result["roll"] == 0
