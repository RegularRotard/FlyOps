"""Tests for flight planning overview warnings and indicators."""

from datetime import date, time

from app.leg_summary import (
    _etd_indicator,
    _etd_text,
    _leg_warnings,
    _planning_status,
)


def make_leg(**overrides):
    leg = {
        "Flight Type": "Charter",
        "Departure": "HTZA",
        "Destination": "LZ001",
        "ETD Date": date(2026, 11, 3),
        "ETD Time": time(8, 0),
        "Flight Minutes": 30.0,
        "_eti_origin": "AUTO",
        "_eti_review": False,
        "_etd_origin": "AUTO",
    }

    leg.update(overrides)
    return leg


def test_automatic_departure_indicator():
    leg = make_leg()

    assert _etd_indicator(leg, 1) == "🔵 AUTO"


def test_manual_departure_indicator():
    leg = make_leg(_etd_origin="MANUAL")

    assert _etd_indicator(leg, 1) == "🟠 MANUAL"


def test_adjusted_departure_indicator():
    leg = make_leg(_etd_origin="ADJUSTED")

    assert _etd_indicator(leg, 1) == "⚠️ ADJUSTED"


def test_first_departure_is_scheduled():
    leg = make_leg()

    assert _etd_indicator(leg, 0) == "🟣 SCHEDULED"


def test_departure_time_format():
    leg = make_leg()

    assert _etd_text(leg) == "08:00"


def test_missing_departure_warning():
    leg = make_leg(Departure="")

    warnings = _leg_warnings(leg, (), 0)

    assert "Departure location missing" in warnings


def test_missing_destination_warning():
    leg = make_leg(Destination="")

    warnings = _leg_warnings(leg, (), 0)

    assert "Destination location missing" in warnings


def test_manual_eti_review_warning():
    leg = make_leg(_eti_review=True)

    warnings = _leg_warnings(leg, (), 1)

    assert "Manual ETI requires review" in warnings


def test_adjusted_etd_warning():
    leg = make_leg(_etd_origin="ADJUSTED")

    warnings = _leg_warnings(leg, (), 1)

    assert "Departure adjusted due to scheduling conflict" in warnings


def test_unavailable_eti_warning():
    leg = make_leg(_eti_origin="UNAVAILABLE")

    warnings = _leg_warnings(leg, (), 1)

    assert "Automatic ETI unavailable" in warnings


def test_invalid_duration_warning():
    leg = make_leg(**{"Flight Minutes": 0})

    warnings = _leg_warnings(leg, (), 1)

    assert "Valid flight duration required" in warnings


def test_no_issues_status():
    leg = make_leg()

    assert _planning_status(leg, (), 1) == ("✅ No flagged issues")


def test_warning_status():
    leg = make_leg(Destination="")

    assert _planning_status(leg, (), 1).startswith("⚠️")
