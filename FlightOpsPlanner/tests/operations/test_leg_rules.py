"""Flight-leg schedule constraints, including midnight rollover."""

from datetime import date, time

from app.leg_rules import apply_scenic_destination, enforce_minimum_etd


def _leg(day, departure_time, minutes, flight_type="Charter"):
    return {
        "ETD Date": day,
        "ETD Time": departure_time,
        "Flight Minutes": minutes,
        "Flight Type": flight_type,
        "Departure": "HTZA",
        "Destination": "HTDA",
    }


def test_scenic_destination_follows_departure():
    leg = _leg(date(2026, 11, 3), time(8), 15, "Scenic")
    apply_scenic_destination(leg)
    assert leg["Destination"] == "HTZA"
    leg["Departure"] = "OTHER"
    apply_scenic_destination(leg)
    assert leg["Destination"] == "OTHER"


def test_non_scenic_destination_preserved():
    leg = _leg(date(2026, 11, 3), time(8), 45)
    apply_scenic_destination(leg)
    assert leg["Destination"] == "HTDA"


def test_next_leg_etd_clamped_to_previous_eta():
    previous = _leg(date(2026, 11, 3), time(8), 30)
    current = _leg(date(2026, 11, 3), time(8, 10), 30)
    assert enforce_minimum_etd(current, previous)
    assert current["ETD Time"] == time(8, 30)


def test_later_etd_is_preserved():
    previous = _leg(date(2026, 11, 3), time(8), 30)
    current = _leg(date(2026, 11, 3), time(9), 30)
    assert not enforce_minimum_etd(current, previous)
    assert current["ETD Time"] == time(9)


def test_midnight_rollover_clamps_date_and_time():
    previous = _leg(date(2026, 11, 3), time(23, 50), 25)
    current = _leg(date(2026, 11, 3), time(23, 59), 30)
    assert enforce_minimum_etd(current, previous)
    assert current["ETD Date"] == date(2026, 11, 4)
    assert current["ETD Time"] == time(0, 15)


def test_first_leg_has_no_predecessor_restriction():
    leg = _leg(date(2026, 11, 3), time(8), 15)
    assert not enforce_minimum_etd(leg, None)
