"""Automatic estimated flight time calculations and overrides."""

from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isfinite


class ETISource(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ETIResult:
    """Resolved ETI and its origin."""

    minutes: float | None
    source: ETISource
    calculated_minutes: float | None
    requires_review: bool = False


def calculate_eti(
    distance_nm: float,
    groundspeed_knots: float,
) -> int:
    """Calculate whole-minute ETI, rounded upward."""

    if not isfinite(distance_nm) or distance_nm < 0:
        raise ValueError("Distance must be finite and non-negative.")

    if not isfinite(groundspeed_knots) or groundspeed_knots <= 0:
        raise ValueError("Groundspeed must be finite and positive.")

    return ceil(distance_nm / groundspeed_knots * 60)


def resolve_eti(
    *,
    flight_type: str,
    distance_nm: float | None,
    groundspeed_knots: float | None,
    manual_minutes: float | None = None,
    scheduled_minutes: int | None = None,
    route_changed: bool = False,
) -> ETIResult:
    """Resolve automatic, manual or scheduled flight duration."""

    if flight_type == "Scenic":
        if scheduled_minutes not in (15, 30):
            raise ValueError("Scenic duration must be 15 or 30 minutes.")

        return ETIResult(
            minutes=float(scheduled_minutes),
            source=ETISource.SCHEDULED,
            calculated_minutes=None,
        )

    calculated = None

    if distance_nm is not None and groundspeed_knots is not None:
        calculated = float(calculate_eti(distance_nm, groundspeed_knots))

    if manual_minutes is not None:
        if not isfinite(manual_minutes) or manual_minutes <= 0:
            raise ValueError("Manual ETI must be finite and positive.")

        return ETIResult(
            minutes=float(manual_minutes),
            source=ETISource.MANUAL,
            calculated_minutes=calculated,
            requires_review=route_changed,
        )

    if calculated is not None:
        return ETIResult(
            minutes=calculated,
            source=ETISource.AUTO,
            calculated_minutes=calculated,
        )

    return ETIResult(
        minutes=None,
        source=ETISource.UNAVAILABLE,
        calculated_minutes=None,
    )
