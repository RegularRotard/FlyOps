"""Saved-location choices for FlyOps flight-planning controls."""

from dataclasses import dataclass
from pathlib import Path

from flightops.locations.catalog import list_locations

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "databases" / "flightops.db"

CATEGORY_ICONS = {
    "Airport": "✈️",
    "Landing Zone": "🚁",
    "Refuelling Point": "⛽",
    "Waypoint": "📍",
}


@dataclass(frozen=True)
class LocationChoice:
    """A saved location available for flight planning."""

    location_id: str
    name: str
    category: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        """Human-readable location name."""

        icon = CATEGORY_ICONS.get(self.category, "📍")

        return f"{icon} {self.name} - {self.location_id}"


def load_location_choices(
    db_path: Path = DATABASE_PATH,
) -> tuple[LocationChoice, ...]:
    """Load saved locations without changing their identifiers."""

    locations = list_locations(db_path)

    return tuple(
        LocationChoice(
            location_id=location.location_id,
            name=location.name,
            category=location.category,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        for location in locations
    )


def location_options(
    locations: tuple[LocationChoice, ...],
    current_id: str = "",
) -> tuple[str, ...]:
    """Return selector IDs, preserving any existing draft selection."""

    identifiers = [""]

    identifiers.extend(location.location_id for location in locations)

    if current_id and current_id not in identifiers:
        identifiers.append(current_id)

    return tuple(identifiers)


def format_location_option(
    location_id: str,
    locations: tuple[LocationChoice, ...],
) -> str:
    """Format a saved location for a Streamlit selector."""

    if not location_id:
        return "Select a location..."

    for location in locations:
        if location.location_id == location_id:
            return location.label

    return f"⚠️ {location_id} — Not found in location database"
