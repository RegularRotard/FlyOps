"""Location database regression tests independent of production flightops.db."""

import csv
import sqlite3

import pytest

from flightops.locations.catalog import add_location, import_seed, list_locations


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "flightops.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE aircraft_test_sentinel (value TEXT)")
        conn.execute("INSERT INTO aircraft_test_sentinel VALUES ('unchanged')")
    return path


def make_csv(path, category, ident):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "location_id",
                "name",
                "category",
                "latitude",
                "longitude",
                "verification_status",
                "source_document",
                "source_valid_until",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "location_id": ident,
                "name": f"Sample {category}",
                "category": category,
                "latitude": -6.2,
                "longitude": 39.2,
                "verification_status": "Source expired - review required",
                "source_document": "sample.pdf",
                "source_valid_until": "2026-10-01",
            }
        )


def test_import_repeat_safe_and_existing_tables_intact(db, tmp_path):
    airports = tmp_path / "airports.csv"
    waypoints = tmp_path / "waypoints.csv"
    make_csv(airports, "Airport", "HTZA")
    make_csv(waypoints, "Waypoint", "VRP-01")
    assert import_seed(db, airports, waypoints) == {"inserted": 2, "already_present": 0}
    assert import_seed(db, airports, waypoints) == {"inserted": 0, "already_present": 2}
    assert len(list_locations(db)) == 2
    with sqlite3.connect(db) as conn:
        assert (
            conn.execute("SELECT value FROM aircraft_test_sentinel").fetchone()[0]
            == "unchanged"
        )


def test_user_location_search_and_filters(db):
    ident = add_location(
        db,
        name="Beach landing",
        category="Landing Zone",
        latitude=-6.1,
        longitude=39.3,
        notes="Site not verified",
    )
    assert ident.startswith("LOC-")
    result = list_locations(db, search="beach", categories=("Landing Zone",))
    assert len(result) == 1
    assert result[0].verification_status == "Unverified"
    assert list_locations(db, categories=()) == ()
    assert list_locations(db, search="missing") == ()


@pytest.mark.parametrize("latitude,longitude", [(91, 0), (0, -181), (float("nan"), 0)])
def test_invalid_coordinates_rejected(db, latitude, longitude):
    with pytest.raises(ValueError):
        add_location(
            db,
            name="Bad point",
            category="Waypoint",
            latitude=latitude,
            longitude=longitude,
        )
