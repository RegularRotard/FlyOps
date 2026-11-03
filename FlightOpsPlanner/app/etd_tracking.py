"""Track automatic, manual and adjusted flight departure times."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class ETDSource(StrEnum):
    SCHEDULED = "SCHEDULED"
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    ADJUSTED = "ADJUSTED"


@dataclass(frozen=True)
class ETDResult:
    """Effective departure and its provenance."""

    departure: datetime
    source: ETDSource
    requested: datetime | None = None


def round_up_to_minute(value: datetime) -> datetime:
    """Round a datetime up to the next whole minute."""

    rounded = value.replace(second=0, microsecond=0)

    if rounded < value:
        rounded += timedelta(minutes=1)

    return rounded


def resolve_etd(
    *,
    current: datetime,
    previous_eta: datetime | None,
    manual_requested: datetime | None = None,
) -> ETDResult:
    """Resolve departure while preserving a deliberate manual request."""

    if previous_eta is None:
        return ETDResult(
            departure=current,
            source=ETDSource.SCHEDULED,
        )

    earliest = round_up_to_minute(previous_eta)

    if manual_requested is not None:
        if manual_requested < earliest:
            return ETDResult(
                departure=earliest,
                source=ETDSource.ADJUSTED,
                requested=manual_requested,
            )

        return ETDResult(
            departure=manual_requested,
            source=ETDSource.MANUAL,
            requested=manual_requested,
        )

    return ETDResult(
        departure=earliest,
        source=ETDSource.AUTO,
    )
