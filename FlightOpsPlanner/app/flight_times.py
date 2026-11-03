"""Flight-leg time calculations for the FlyOps interface."""

from datetime import date, datetime, time, timedelta
from math import isfinite


def calculate_eta(
    etd_date: date,
    etd_time: time,
    eti_minutes: float,
) -> datetime:
    """Calculate ETA from local departure date/time and planned duration.

    Returns a naive local datetime. Timezone conversion is not performed.
    """

    if not isfinite(eti_minutes) or eti_minutes <= 0:
        raise ValueError("ETI must be a positive, finite duration.")

    departure = datetime.combine(etd_date, etd_time)

    return departure + timedelta(minutes=eti_minutes)


def format_eta(eta: datetime, departure_date: date) -> str:
    """Format ETA and identify arrival on a different calendar day."""

    formatted = eta.strftime("%H:%M")

    days_difference = (eta.date() - departure_date).days

    if days_difference > 0:
        return f"{formatted} (+{days_difference} day)"

    return formatted
