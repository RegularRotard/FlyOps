"""Tests for the flight-plan map renderer."""

from types import SimpleNamespace

import folium
import pandas as pd
import pytest

from app.flight_plan_map import build_flight_plan_map


@pytest.fixture
def locations():
    return {
        "HTZA": SimpleNamespace(
            name="Zanzibar",
            latitude=-6.221944,
            longitude=39.224444,
        ),
        "HTDA": SimpleNamespace(
            name="Dar es Salaam",
            latitude=-6.878056,
            longitude=39.202500,
        ),
    }


def make_leg(
    *,
    flight_type="Charter",
    departure="HTZA",
    destination="HTDA",
    minutes=30.0,
):
    return pd.DataFrame(
        [
            {
                "Leg": "LEG-001",
                "Flight Type": flight_type,
                "Departure": departure,
                "Destination": destination,
                "Flight Minutes": minutes,
                "ETD Date": "2026-11-03",
                "ETD Time": "08:00",
                "ETA": "2026-11-03T08:30",
            }
        ]
    )


def test_charter_route_drawn(locations):
    map_object, warnings = build_flight_plan_map(
        make_leg(),
        locations,
        100,
    )

    routes = [
        child
        for child in map_object._children.values()
        if isinstance(child, folium.vector_layers.PolyLine)
    ]

    assert len(routes) == 1
    assert warnings == []


def test_scenic_circle_drawn(locations):
    map_object, warnings = build_flight_plan_map(
        make_leg(
            flight_type="Scenic",
            departure="HTZA",
            destination="HTZA",
            minutes=15,
        ),
        locations,
        100,
    )

    circles = [
        child
        for child in map_object._children.values()
        if isinstance(child, folium.vector_layers.Circle)
    ]

    assert len(circles) == 1
    assert warnings == []


def test_thirty_minute_scenic_circle(locations):
    map_object, _ = build_flight_plan_map(
        make_leg(
            flight_type="Scenic",
            departure="HTZA",
            destination="HTZA",
            minutes=30,
        ),
        locations,
        100,
    )

    circles = [
        child
        for child in map_object._children.values()
        if isinstance(child, folium.vector_layers.Circle)
    ]

    assert len(circles) == 1

    assert circles[0].options["radius"] == pytest.approx(25 * 1852)


def test_unknown_destination_warns(locations):
    _, warnings = build_flight_plan_map(
        make_leg(destination="UNKNOWN"),
        locations,
        100,
    )

    assert len(warnings) == 1
    assert "UNKNOWN" in warnings[0]


def test_invalid_scenic_duration_warns(locations):
    _, warnings = build_flight_plan_map(
        make_leg(
            flight_type="Scenic",
            destination="HTZA",
            minutes=20,
        ),
        locations,
        100,
    )

    assert len(warnings) == 1
    assert "15 or 30" in warnings[0]


def test_invalid_speed_rejected(locations):
    with pytest.raises(ValueError):
        build_flight_plan_map(
            make_leg(),
            locations,
            0,
        )
