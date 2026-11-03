"""Tests for the compact flight-leg overview."""

from datetime import date, time

from app.leg_summary import (
    _eta_text,
    _eti_indicator,
    _location_name,
)
from app.location_choices import LocationChoice


def make_leg(
    flight_type="Charter",
    minutes=30,
    origin="AUTO",
    review=False,
):
    return {
        "_uid": "test-leg",
        "Flight Type": flight_type,
        "Departure": "HTZA",
        "Destination": "HTDA",
        "ETD Date": date(2026, 11, 3),
        "ETD Time": time(8, 0),
        "Flight Minutes": minutes,
        "_eti_origin": origin,
        "_eti_review": review,
    }


def test_auto_indicator():
    leg = make_leg(origin="AUTO")

    assert _eti_indicator(leg) == "🔵 AUTO"


def test_manual_indicator():
    leg = make_leg(origin="MANUAL")

    assert _eti_indicator(leg) == "🟠 MANUAL"


def test_manual_review_indicator():
    leg = make_leg(origin="MANUAL", review=True)

    assert "⚠️" in _eti_indicator(leg)


def test_scenic_indicator():
    leg = make_leg(
        flight_type="Scenic",
        minutes=15,
    )

    assert _eti_indicator(leg) == "🟣 SCHEDULED"


def test_eta_calculated():
    leg = make_leg(minutes=30)

    assert _eta_text(leg) == "08:30"


def test_eta_crosses_midnight():
    leg = make_leg(minutes=30)
    leg["ETD Time"] = time(23, 45)

    assert _eta_text(leg) == "00:15"


def test_location_name():
    locations = (
        LocationChoice(
            location_id="HTZA",
            name="Zanzibar Airport",
            category="Airport",
            latitude=-6.22,
            longitude=39.22,
        ),
    )

    assert _location_name("HTZA", locations) == "Zanzibar Airport"


def test_unknown_location_preserved():
    assert _location_name("UNKNOWN", ()) == "UNKNOWN"


def test_empty_location():
    assert _location_name("", ()) == "Not selected"
