"""Tests for Scenic radius calculations."""

import math

import folium
import pytest

from app.scenic_map import add_scenic_radius
from flightops.locations.scenic_radius import (
    calculate_scenic_radius,
    scenic_radius_metres,
)


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (15, 12.5),
        (30, 25.0),
    ],
)
def test_radius_at_100_knots(duration, expected):
    assert calculate_scenic_radius(duration, 100) == pytest.approx(expected)


def test_radius_changes_with_speed():
    assert calculate_scenic_radius(30, 120) == pytest.approx(30.0)


def test_radius_metres():
    assert scenic_radius_metres(15, 100) == pytest.approx(12.5 * 1852.0)


@pytest.mark.parametrize("duration", [0, 10, 20, 45])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError):
        calculate_scenic_radius(duration, 100)


@pytest.mark.parametrize("speed", [0, -10, math.inf, math.nan])
def test_invalid_speed_rejected(speed):
    with pytest.raises(ValueError):
        calculate_scenic_radius(15, speed)


def test_circle_added_to_map():
    map_object = folium.Map(location=[-6.22, 39.22])

    add_scenic_radius(
        map_object,
        latitude=-6.22,
        longitude=39.22,
        duration_minutes=15,
        cruise_speed_knots=100,
        leg_id="LEG-001",
    )

    circles = [
        child
        for child in map_object._children.values()
        if isinstance(child, folium.vector_layers.Circle)
    ]

    assert len(circles) == 1
    assert circles[0].options["radius"] == pytest.approx(12.5 * 1852.0)
