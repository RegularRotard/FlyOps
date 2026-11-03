"""Self-contained SQLite location catalogue for the FlyOps prototype.

Uses its own `map_locations` table in the existing database; it does not
change or recreate aircraft, revision, or flight operation tables.
"""

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

CATEGORIES = ("Airport", "Landing Zone", "Refuelling Point", "Waypoint")


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str
    category: str
    latitude: float
    longitude: float
    verification_status: str
    source_document: str = ""
    source_valid_until: str = ""
    notes: str = ""
    details: dict | None = None


def _open(db_path: Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Missing database directory: {path.parent}")
    if not path.is_file():
        raise FileNotFoundError(f"Existing FlyOps database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialise_locations(db_path: Path) -> None:
    """Add location tables only; preserve the existing FlyOps schema."""
    with _open(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS map_locations (
                location_id TEXT PRIMARY KEY,
                name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                category TEXT NOT NULL,
                latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
                longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
                verification_status TEXT NOT NULL,
                source_document TEXT NOT NULL DEFAULT '',
                source_valid_until TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_map_locations_name
            ON map_locations(name COLLATE NOCASE)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_map_locations_category
            ON map_locations(category)
        """)


def validate_location(
    name: str, category: str, latitude: float, longitude: float
) -> None:
    if not name or not name.strip():
        raise ValueError("Location name is required")
    if category not in CATEGORIES:
        raise ValueError(f"Unrecognized location category: {category}")
    from math import isfinite

    if not all(isfinite(value) for value in (latitude, longitude)):
        raise ValueError("Coordinates must be finite")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Coordinates are outside valid latitude/longitude ranges")


def add_location(
    db_path: Path,
    *,
    name: str,
    category: str,
    latitude: float,
    longitude: float,
    notes: str = "",
) -> str:
    """Save a manually selected location as unverified; returns persistent ID."""
    validate_location(name, category, latitude, longitude)
    initialise_locations(db_path)
    location_id = f"LOC-{uuid4().hex[:16].upper()}"
    with _open(db_path) as conn:
        conn.execute(
            """INSERT INTO map_locations
                (location_id,name,category,latitude,longitude,verification_status,notes)
                VALUES (?,?,?,?,?,?,?)""",
            (
                location_id,
                name.strip(),
                category,
                latitude,
                longitude,
                "Unverified",
                notes.strip(),
            ),
        )
    return location_id


def import_seed(db_path: Path, airport_csv: Path, waypoint_csv: Path) -> dict[str, int]:
    """Idempotently import both source files without overwriting saved edits.

    Import is additive: an existing location_id is left intact. Airports and
    waypoints keep all source columns in details_json.
    """
    counts = {"inserted": 0, "already_present": 0}
    # Parse and validate everything before opening a write transaction.
    prepared = []
    for category, path in (("Airport", airport_csv), ("Waypoint", waypoint_csv)):
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                latitude = float(row["latitude"])
                longitude = float(row["longitude"])
                validate_location(row["name"], category, latitude, longitude)
                if row.get("category") != category:
                    raise ValueError(
                        f"Unexpected category for {row.get('location_id')}"
                    )
                prepared.append(
                    (
                        row["location_id"],
                        row["name"],
                        category,
                        latitude,
                        longitude,
                        row.get(
                            "verification_status", "Source expired - review required"
                        ),
                        row.get("source_document", ""),
                        row.get("source_valid_until", ""),
                        row.get("notes", ""),
                        json.dumps(row, ensure_ascii=False),
                    )
                )
    if len({r[0] for r in prepared}) != len(prepared):
        raise ValueError("Seed files contain duplicate location IDs")
    initialise_locations(db_path)
    with _open(db_path) as conn:
        for row in prepared:
            result = conn.execute(
                """INSERT OR IGNORE INTO map_locations
                (location_id,name,category,latitude,longitude,verification_status,
                 source_document,source_valid_until,notes,details_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                row,
            )
            counts["inserted" if result.rowcount else "already_present"] += 1
    return counts


def list_locations(
    db_path: Path,
    *,
    search: str = "",
    categories: tuple[str, ...] | None = None,
) -> tuple[Location, ...]:
    initialise_locations(db_path)
    clauses = []
    params: list[str] = []
    if search.strip():
        # No user input is interpolated into SQL.
        clauses.append("(lower(name) LIKE ? OR lower(location_id) LIKE ?)")
        needle = f"%{search.strip().lower()}%"
        params.extend((needle, needle))
    if categories is not None:
        if not categories:
            return ()
        if not set(categories).issubset(CATEGORIES):
            raise ValueError("Unknown category filter")
        clauses.append("category IN (" + ",".join("?" for _ in categories) + ")")
        params.extend(categories)
    sql = "SELECT * FROM map_locations"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY category, name COLLATE NOCASE"
    with _open(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return tuple(
        Location(
            location_id=row["location_id"],
            name=row["name"],
            category=row["category"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            verification_status=row["verification_status"],
            source_document=row["source_document"],
            source_valid_until=row["source_valid_until"],
            notes=row["notes"],
            details=json.loads(row["details_json"]),
        )
        for row in rows
    )
