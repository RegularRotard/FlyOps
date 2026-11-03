"""Pure draft-flight-leg rules (independent of Streamlit)."""

from datetime import date, datetime, time, timedelta


def arrival(etd_date: date, etd_time: time, minutes: float) -> datetime:
    """Return ETA using the existing tested time calculator."""
    from app.flight_times import calculate_eta

    return calculate_eta(etd_date, etd_time, minutes)


def earliest_etd(previous: dict | None) -> datetime | None:
    """The prior leg's ETA is the earliest permissible next ETD."""
    if previous is None:
        return None
    return arrival(
        previous["ETD Date"], previous["ETD Time"], previous["Flight Minutes"]
    )


def apply_scenic_destination(leg: dict) -> None:
    """Scenic flights always return to their departure identifier."""
    if leg["Flight Type"] == "Scenic":
        leg["Destination"] = leg["Departure"]


def enforce_minimum_etd(leg: dict, previous: dict | None) -> bool:
    """Clamp ETD to previous ETA if too early. Return whether changed."""
    minimum = earliest_etd(previous)
    if minimum is None:
        return False
    selected = datetime.combine(leg["ETD Date"], leg["ETD Time"])
    if selected >= minimum:
        return False
    # Round upward to the next whole minute, never backward.
    adjusted = minimum.replace(second=0, microsecond=0)

    if adjusted < minimum:
        adjusted += timedelta(minutes=1)

    leg["ETD Date"] = adjusted.date()
    leg["ETD Time"] = adjusted.time()
    return True
