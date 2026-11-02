"""Tests for aircraft revision database constraints."""

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session

from flightops.database.base import Base
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftProfileRevision,
    AircraftVariant,
    Manufacturer,
)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'revision_constraints.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


def test_revision_numbers_have_unique_constraint(database):
    inspector = inspect(database)

    constraints = inspector.get_unique_constraints(
        AircraftProfileRevision.__tablename__
    )

    indexes = inspector.get_indexes(AircraftProfileRevision.__tablename__)

    required_columns = {
        "profile_id",
        "revision_number",
    }

    has_constraint = any(
        set(constraint["column_names"]) == required_columns
        for constraint in constraints
    )

    has_unique_index = any(
        index.get("unique") and set(index["column_names"]) == required_columns
        for index in indexes
    )

    assert has_constraint or has_unique_index, (
        "Aircraft revision numbers must be unique per profile."
    )


def test_aircraft_profile_can_be_created(database):
    with Session(database) as session:
        manufacturer = Manufacturer(name="Test Manufacturer")

        family = AircraftFamily(
            manufacturer=manufacturer,
            name="Test Family",
        )

        variant = AircraftVariant(
            family=family,
            designation="Test Variant",
        )

        aircraft = AircraftProfile(
            variant=variant,
            registration="5H-TEST",
            serial_number="TEST-001",
        )

        session.add(aircraft)
        session.commit()

        assert aircraft.id is not None
