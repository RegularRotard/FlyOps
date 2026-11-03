"""Tests for automatic, manual and adjusted departure times."""

from datetime import datetime

from app.etd_tracking import (
    ETDSource,
    resolve_etd,
    round_up_to_minute,
)


def dt(hour, minute, day=3):
    return datetime(2026, 11, day, hour, minute)


def test_first_leg_is_scheduled():
    result = resolve_etd(
        current=dt(8, 0),
        previous_eta=None,
    )

    assert result.source == ETDSource.SCHEDULED
    assert result.departure == dt(8, 0)


def test_automatic_departure_follows_previous_eta():
    result = resolve_etd(
        current=dt(9, 30),
        previous_eta=dt(9, 0),
    )

    assert result.source == ETDSource.AUTO
    assert result.departure == dt(9, 0)


def test_automatic_departure_moves_when_eta_changes():
    result = resolve_etd(
        current=dt(9, 0),
        previous_eta=dt(9, 15),
    )

    assert result.departure == dt(9, 15)


def test_manual_departure_preserved():
    result = resolve_etd(
        current=dt(9, 30),
        previous_eta=dt(9, 0),
        manual_requested=dt(9, 30),
    )

    assert result.source == ETDSource.MANUAL
    assert result.departure == dt(9, 30)


def test_conflicting_manual_departure_adjusted():
    result = resolve_etd(
        current=dt(9, 0),
        previous_eta=dt(9, 15),
        manual_requested=dt(9, 0),
    )

    assert result.source == ETDSource.ADJUSTED
    assert result.departure == dt(9, 15)
    assert result.requested == dt(9, 0)


def test_manual_request_remains_available():
    requested = dt(9, 0)

    result = resolve_etd(
        current=dt(9, 15),
        previous_eta=dt(9, 30),
        manual_requested=requested,
    )

    assert result.departure == dt(9, 30)
    assert result.requested == requested


def test_reset_to_auto_uses_previous_eta():
    result = resolve_etd(
        current=dt(10, 0),
        previous_eta=dt(9, 15),
        manual_requested=None,
    )

    assert result.source == ETDSource.AUTO
    assert result.departure == dt(9, 15)


def test_midnight_rollover():
    result = resolve_etd(
        current=dt(23, 30),
        previous_eta=dt(0, 15, day=4),
    )

    assert result.departure == dt(0, 15, day=4)


def test_round_up_seconds():
    value = datetime(2026, 11, 3, 9, 15, 30)

    assert round_up_to_minute(value) == dt(9, 16)


def test_exact_minute_not_rounded():
    assert round_up_to_minute(dt(9, 15)) == dt(9, 15)
