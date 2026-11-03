"""Tests for FlyOps flight timing calculations."""

from datetime import date, time

import pytest

from app.flight_times import calculate_eta, format_eta


def test_standard_flight_eta():
    eta = calculate_eta(
        date(2026, 11, 3),
        time(8, 0),
        15,
    )

    assert eta.hour == 8
    assert eta.minute == 15


def test_forty_five_minute_flight():
    eta = calculate_eta(
        date(2026, 11, 3),
        time(9, 0),
        45,
    )

    assert eta.hour == 9
    assert eta.minute == 45


def test_midnight_rollover():
    eta = calculate_eta(
        date(2026, 11, 3),
        time(23, 45),
        30,
    )

    assert eta.date() == date(2026, 11, 4)
    assert eta.hour == 0
    assert eta.minute == 15


def test_midnight_rollover_display():
    departure_date = date(2026, 11, 3)

    eta = calculate_eta(
        departure_date,
        time(23, 45),
        30,
    )

    assert format_eta(eta, departure_date) == "00:15 (+1 day)"


def test_zero_duration_rejected():
    with pytest.raises(ValueError, match="positive"):
        calculate_eta(
            date(2026, 11, 3),
            time(8, 0),
            0,
        )


def test_negative_duration_rejected():
    with pytest.raises(ValueError, match="positive"):
        calculate_eta(
            date(2026, 11, 3),
            time(8, 0),
            -10,
        )


def test_nonfinite_duration_rejected():
    with pytest.raises(ValueError, match="finite"):
        calculate_eta(
            date(2026, 11, 3),
            time(8, 0),
            float("nan"),
        )
