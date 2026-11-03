"""Tests for creating locations from Flight Planning."""

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.new_location_dialog import (
    CREATABLE_CATEGORIES,
    save_new_location,
    valid_coordinates,
)
from flightops.locations.catalog import list_locations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS = PROJECT_ROOT / "tests" / "ui" / "flight_editor_harness.py"


def test_valid_coordinates():
    assert valid_coordinates(-6.22, 39.22)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91, 39),
        (-91, 39),
        (-6, 181),
        (-6, -181),
        (math.nan, 39),
        (-6, math.inf),
    ],
)
def test_invalid_coordinates(latitude, longitude):
    assert not valid_coordinates(latitude, longitude)


def test_airport_not_manually_creatable():
    assert "Airport" not in CREATABLE_CATEGORIES


def test_name_required(tmp_path):
    with pytest.raises(ValueError, match="name"):
        save_new_location(
            name=" ",
            category=CREATABLE_CATEGORIES[0],
            latitude=-6.22,
            longitude=39.22,
            db_path=tmp_path / "test.db",
        )


def test_location_can_be_saved(tmp_path):
    db_path = tmp_path / "locations.db"

    # The catalogue requires an existing SQLite database.
    # Create an isolated test database rather than using live data.
    import sqlite3

    with sqlite3.connect(db_path):
        pass

    new_id = save_new_location(
        name="Test Landing Zone",
        category="Landing Zone",
        latitude=-6.22,
        longitude=39.22,
        notes="Demonstration record",
        db_path=db_path,
    )

    locations = list_locations(db_path)

    saved = next(location for location in locations if location.location_id == new_id)

    assert saved.name == "Test Landing Zone"
    assert saved.category == "Landing Zone"
    assert saved.latitude == pytest.approx(-6.22)
    assert saved.longitude == pytest.approx(39.22)


def test_new_location_buttons_visible():
    app = AppTest.from_file(
        str(HARNESS),
        default_timeout=20,
    ).run()

    assert not app.exception

    labels = [button.label for button in app.button]

    assert "➕ New Departure" in labels
    assert "➕ New Destination" in labels
