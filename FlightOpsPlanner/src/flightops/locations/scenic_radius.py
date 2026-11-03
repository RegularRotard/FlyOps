"""Calculate theoretical Scenic flight operating radii."""

from math import isfinite

METRES_PER_NAUTICAL_MILE = 1852.0
SCENIC_DURATIONS = (15, 30)


def calculate_scenic_radius(
    duration_minutes: int,
    cruise_speed_knots: float,
) -> float:
    """Calculate maximum theoretical out-and-back radius in NM."""

    if duration_minutes not in SCENIC_DURATIONS:
        raise ValueError("Scenic duration must be 15 or 30 minutes.")

    if not isfinite(cruise_speed_knots) or cruise_speed_knots <= 0:
        raise ValueError("Cruise speed must be positive and finite.")

    return cruise_speed_knots * duration_minutes / 120.0


def scenic_radius_metres(
    duration_minutes: int,
    cruise_speed_knots: float,
) -> float:
    """Convert Scenic operating radius to metres."""

    return (
        calculate_scenic_radius(
            duration_minutes,
            cruise_speed_knots,
        )
        * METRES_PER_NAUTICAL_MILE
    )
