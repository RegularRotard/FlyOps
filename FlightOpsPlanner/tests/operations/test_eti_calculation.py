"""Tests for automatic and manually overridden ETI."""

import pytest

from flightops.operations.services.eti_calculation import (
    ETISource,
    calculate_eti,
    resolve_eti,
)


def test_automatic_eti():
    assert calculate_eti(40, 100) == 24


def test_automatic_eti_rounds_up():
    assert calculate_eti(41, 100) == 25


def test_speed_changes_automatic_eti():
    slow = resolve_eti(
        flight_type="Charter",
        distance_nm=40,
        groundspeed_knots=80,
    )

    fast = resolve_eti(
        flight_type="Charter",
        distance_nm=40,
        groundspeed_knots=120,
    )

    assert slow.minutes == 30
    assert fast.minutes == 20
    assert slow.source == ETISource.AUTO
    assert fast.source == ETISource.AUTO


def test_manual_override_preserved():
    result = resolve_eti(
        flight_type="Charter",
        distance_nm=40,
        groundspeed_knots=100,
        manual_minutes=30,
    )

    assert result.minutes == 30
    assert result.calculated_minutes == 24
    assert result.source == ETISource.MANUAL


def test_manual_override_requires_review_after_route_change():
    result = resolve_eti(
        flight_type="Charter",
        distance_nm=80,
        groundspeed_knots=100,
        manual_minutes=30,
        route_changed=True,
    )

    assert result.minutes == 30
    assert result.calculated_minutes == 48
    assert result.requires_review


def test_reset_to_auto():
    result = resolve_eti(
        flight_type="Charter",
        distance_nm=40,
        groundspeed_knots=100,
        manual_minutes=None,
    )

    assert result.minutes == 24
    assert result.source == ETISource.AUTO


@pytest.mark.parametrize("duration", [15, 30])
def test_scenic_is_scheduled(duration):
    result = resolve_eti(
        flight_type="Scenic",
        distance_nm=0,
        groundspeed_knots=100,
        scheduled_minutes=duration,
    )

    assert result.minutes == duration
    assert result.source == ETISource.SCHEDULED


def test_missing_calculation_inputs():
    result = resolve_eti(
        flight_type="Charter",
        distance_nm=None,
        groundspeed_knots=100,
    )

    assert result.minutes is None
    assert result.source == ETISource.UNAVAILABLE


@pytest.mark.parametrize("speed", [0, -1, float("nan"), float("inf")])
def test_invalid_speed_rejected(speed):
    with pytest.raises(ValueError):
        calculate_eti(40, speed)


def test_negative_distance_rejected():
    with pytest.raises(ValueError):
        calculate_eti(-10, 100)


def test_invalid_manual_override_rejected():
    with pytest.raises(ValueError):
        resolve_eti(
            flight_type="Ferry",
            distance_nm=40,
            groundspeed_knots=100,
            manual_minutes=-5,
        )
