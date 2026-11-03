"""Offline location-to-location route calculation tests."""

from datetime import datetime
from math import isfinite

import pytest

from flightops.locations.routing import distance_nm, estimate_route


def test_same_point_has_zero_distance():
    assert distance_nm(-6.2, 39.2, -6.2, 39.2) == pytest.approx(0)


def test_one_degree_equator_about_sixty_nm():
    assert distance_nm(0, 0, 0, 1) == pytest.approx(60.04, abs=0.1)


def test_distance_is_symmetric():
    assert distance_nm(-6, 39, -7, 40) == pytest.approx(distance_nm(-7, 40, -6, 39))


def test_estimate_eti_and_eta():
    result = estimate_route(((0, 0), (0, 1)), 120, datetime(2026, 11, 3, 8))
    assert result.estimated_minutes == 31
    assert result.eta == datetime(2026, 11, 3, 8, 31)


def test_midnight_rollover():
    result = estimate_route(((0, 0), (0, 1)), 120, datetime(2026, 11, 3, 23, 45))
    assert result.eta == datetime(2026, 11, 4, 0, 16)


def test_multiple_points_total_is_sum_of_sections():
    points = ((0, 0), (0, 1), (1, 1))
    result = estimate_route(points, 100, datetime(2026, 11, 3, 8))
    assert result.distance_nm == pytest.approx(
        distance_nm(0, 0, 0, 1) + distance_nm(0, 1, 1, 1)
    )


@pytest.mark.parametrize("speed", [0, -1, float("inf"), float("nan")])
def test_invalid_groundspeed_rejected(speed):
    with pytest.raises(ValueError, match="groundspeed"):
        estimate_route(((0, 0), (0, 1)), speed, datetime(2026, 11, 3, 8))


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), 91, -91])
def test_invalid_latitude_rejected(coordinate):
    with pytest.raises(ValueError, match="Coordinates"):
        distance_nm(coordinate, 0, 0, 0)


def test_single_location_rejected():
    with pytest.raises(ValueError, match="At least"):
        estimate_route(((0, 0),), 100, datetime(2026, 11, 3, 8))


def test_zero_length_route_explained():
    with pytest.raises(ValueError, match="Scenic"):
        estimate_route(((0, 0), (0, 0)), 100, datetime(2026, 11, 3, 8))


def test_result_fields_finite():
    result = estimate_route(((-6.2, 39.2), (-6.8, 39.1)), 90, datetime(2026, 11, 3, 8))
    assert isfinite(result.distance_nm)
    assert result.planned_groundspeed_kt == 90
