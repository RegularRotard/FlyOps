"""Tests for SQLite concurrent aircraft revision writes."""

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import (
    AircraftRevisionService,
)
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
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent_writes.db'}",
        connect_args={"timeout": 0.1},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
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
        aircraft_id = aircraft.id

    yield engine, aircraft_id

    engine.dispose()


def test_database_lock_rejects_second_writer(database):
    engine, aircraft_id = database

    with Session(engine) as session_a, Session(engine) as session_b:
        aircraft_a = session_a.get(AircraftProfile, aircraft_id)
        aircraft_b = session_b.get(AircraftProfile, aircraft_id)

        service_a = AircraftRevisionService(session_a)
        service_b = AircraftRevisionService(session_b)

        # Session A obtains the SQLite write lock.
        service_a.create_revision(
            aircraft_a,
            {"empty_weight_kg": 680},
            "Session A revision",
            expected_revision_id=None,
        )

        # Session B cannot write while A holds the lock.
        with pytest.raises(OperationalError):
            service_b.create_revision(
                aircraft_b,
                {"empty_weight_kg": 685},
                "Session B revision",
                expected_revision_id=None,
            )

        session_b.rollback()
        session_a.commit()

    with Session(engine) as session:
        revisions = list(
            session.scalars(
                select(AircraftProfileRevision).where(
                    AircraftProfileRevision.profile_id == aircraft_id
                )
            )
        )

        assert len(revisions) == 1


def test_database_recovers_after_lock_failure(database):
    engine, aircraft_id = database

    with Session(engine) as session_a, Session(engine) as session_b:
        aircraft_a = session_a.get(AircraftProfile, aircraft_id)
        aircraft_b = session_b.get(AircraftProfile, aircraft_id)

        service_a = AircraftRevisionService(session_a)
        service_b = AircraftRevisionService(session_b)

        first = service_a.create_revision(
            aircraft_a,
            {"empty_weight_kg": 680},
            "Initial revision",
            expected_revision_id=None,
        )

        with pytest.raises(OperationalError):
            service_b.create_revision(
                aircraft_b,
                {"empty_weight_kg": 685},
                "Locked revision",
                expected_revision_id=None,
            )

        session_b.rollback()
        session_a.commit()
        first_id = first.id

    # A fresh transaction should succeed using the latest revision.
    with Session(engine) as session:
        aircraft = session.get(AircraftProfile, aircraft_id)

        AircraftRevisionService(session).create_revision(
            aircraft,
            {"empty_weight_kg": 690},
            "Recovered revision",
            expected_revision_id=first_id,
        )

        session.commit()

    with Session(engine) as session:
        revisions = list(
            session.scalars(
                select(AircraftProfileRevision)
                .where(AircraftProfileRevision.profile_id == aircraft_id)
                .order_by(AircraftProfileRevision.revision_number)
            )
        )

        assert len(revisions) == 2
        assert revisions[0].revision_number == 1
        assert revisions[1].revision_number == 2
