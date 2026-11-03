"""Regression tests for flight schedule timing boundaries."""

from datetime import date, datetime, time, timedelta

from app.leg_rules import enforce_minimum_etd


def make_leg(
    *,
    departure: datetime,
    duration: float,
) -> dict:
    return {
        "ETD Date": departure.date(),
        "ETD Time": departure.time(),
        "Flight Minutes": duration,
    }


def test_next_departure_never_precedes_previous_arrival():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=15.5,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 9, 10),
        duration=30,
    )

    assert enforce_minimum_etd(current, previous)

    assert current["ETD Time"] == time(9, 16)


def test_exact_minute_is_preserved():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=15,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=30,
    )

    assert enforce_minimum_etd(current, previous)

    assert current["ETD Time"] == time(9, 15)


def test_later_etd_remains_unchanged():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=15,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 10, 0),
        duration=30,
    )

    assert not enforce_minimum_etd(current, previous)

    assert current["ETD Time"] == time(10, 0)


def test_departure_rolls_into_next_day():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 23, 50),
        duration=20.5,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 23, 55),
        duration=15,
    )

    assert enforce_minimum_etd(current, previous)

    assert current["ETD Date"] == date(2026, 11, 4)
    assert current["ETD Time"] == time(0, 11)


def test_repeated_scheduling_does_not_shift_departure():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=15.5,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=30,
    )

    assert enforce_minimum_etd(current, previous)

    first_departure = datetime.combine(
        current["ETD Date"],
        current["ETD Time"],
    )

    assert not enforce_minimum_etd(current, previous)

    second_departure = datetime.combine(
        current["ETD Date"],
        current["ETD Time"],
    )

    assert first_departure == second_departure


def test_schedule_can_include_turnaround_time():
    previous = make_leg(
        departure=datetime(2026, 11, 3, 9, 0),
        duration=15,
    )

    current = make_leg(
        departure=datetime(2026, 11, 3, 9, 25),
        duration=30,
    )

    assert not enforce_minimum_etd(current, previous)

    previous_arrival = datetime.combine(
        previous["ETD Date"],
        previous["ETD Time"],
    ) + timedelta(minutes=previous["Flight Minutes"])

    current_departure = datetime.combine(
        current["ETD Date"],
        current["ETD Time"],
    )

    assert current_departure - previous_arrival == timedelta(minutes=10)
