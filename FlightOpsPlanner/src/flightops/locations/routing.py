"""Offline route-distance and time estimates from saved coordinates.

No map tiles, network connection or external navigation service is required.
Straight-line distances and user-supplied planned ground speeds are rough
operations scheduling inputs, not flight navigation or performance approvals.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from math import asin, ceil, cos, isfinite, radians, sin, sqrt

EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True)
class RouteEstimate:
    distance_nm: float
    planned_groundspeed_kt: float
    estimated_minutes: int
    etd: datetime
    eta: datetime


def _valid_coordinate(latitude: float, longitude: float) -> None:
    if not (isfinite(latitude) and isfinite(longitude)):
        raise ValueError("Coordinates must be finite numbers")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Coordinates are outside valid latitude/longitude ranges")


def distance_nm(
    departure_latitude: float,
    departure_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    """Approximate shortest surface distance in nautical miles (haversine)."""
    _valid_coordinate(departure_latitude, departure_longitude)
    _valid_coordinate(destination_latitude, destination_longitude)
    lat1, lon1, lat2, lon2 = map(
        radians,
        (
            departure_latitude,
            departure_longitude,
            destination_latitude,
            destination_longitude,
        ),
    )
    haversine = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    central_angle = 2 * asin(sqrt(min(1.0, max(0.0, haversine))))
    return EARTH_RADIUS_NM * central_angle


def estimate_route(
    points: tuple[tuple[float, float], ...],
    planned_groundspeed_kt: float,
    etd: datetime,
) -> RouteEstimate:
    """Estimate ETI/ETA along one or more consecutive geographic points.

    Rounds ETI *up* to the next whole minute for staff scheduling.
    The speed is a planning assumption, not a verified aircraft capability.
    """
    if len(points) < 2:
        raise ValueError("At least a departure and destination are required")
    if not isfinite(planned_groundspeed_kt) or planned_groundspeed_kt <= 0:
        raise ValueError("Planned groundspeed must be a positive finite number")
    for lat, lon in points:
        _valid_coordinate(lat, lon)

    total_nm = sum(
        distance_nm(first[0], first[1], second[0], second[1])
        for first, second in pairwise(points)
    )
    if total_nm <= 1e-9:
        raise ValueError(
            "Route has zero point-to-point distance. "
            "Scenic flights need a stored route or a fixed 15/30-minute block."
        )
    eti_minutes = ceil(total_nm / planned_groundspeed_kt * 60)
    return RouteEstimate(
        distance_nm=total_nm,
        planned_groundspeed_kt=planned_groundspeed_kt,
        estimated_minutes=eti_minutes,
        etd=etd,
        eta=etd + timedelta(minutes=eti_minutes),
    )
