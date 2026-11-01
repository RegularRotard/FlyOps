"""Verify that saved aircraft revisions cannot be changed or deleted."""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import AircraftRevisionService
from flightops.database.base import Base
from flightops.database.immutability import install_immutability_triggers
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftVariant,
    Manufacturer,
)


@pytest.fixture
def protected_revision():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        install_immutability_triggers(connection)

    with Session(engine) as session:
        manufacturer = Manufacturer(name="Robinson")
        family = AircraftFamily(
            manufacturer=manufacturer,
            name="R44",
        )
        variant = AircraftVariant(
            family=family,
            designation="Raven II",
        )
        profile = AircraftProfile(
            variant=variant,
            registration="5H-TEST",
            serial_number="TEST-001",
        )

        session.add(profile)
        session.flush()

        service = AircraftRevisionService(session)

        revision = service.create_revision(
            profile,
            {"empty_weight_kg": 680},
            "Initial test configuration",
        )

        session.commit()
        revision_id = revision.id

    yield engine, revision_id

    engine.dispose()


def test_historical_revision_cannot_be_updated(protected_revision):
    engine, revision_id = protected_revision

    with pytest.raises(DatabaseError), engine.begin() as connection:
        connection.execute(
            text("""
                    UPDATE aircraft_profile_revisions
                    SET change_description = 'Unauthorized modification'
                    WHERE id = :revision_id
                """),
            {"revision_id": revision_id},
        )


def test_historical_revision_cannot_be_deleted(protected_revision):
    engine, revision_id = protected_revision

    with pytest.raises(DatabaseError), engine.begin() as connection:
        connection.execute(
            text("""
                    DELETE FROM aircraft_profile_revisions
                    WHERE id = :revision_id
                """),
            {"revision_id": revision_id},
        )


def test_revision_remains_unchanged_after_rejected_update(
    protected_revision,
):
    engine, revision_id = protected_revision

    with pytest.raises(DatabaseError), engine.begin() as connection:
        connection.execute(
            text("""
                    UPDATE aircraft_profile_revisions
                    SET change_description = 'Tampered'
                    WHERE id = :revision_id
                """),
            {"revision_id": revision_id},
        )

    with engine.connect() as connection:
        description = connection.scalar(
            text("""
                SELECT change_description
                FROM aircraft_profile_revisions
                WHERE id = :revision_id
            """),
            {"revision_id": revision_id},
        )

    assert description == "Initial test configuration"
