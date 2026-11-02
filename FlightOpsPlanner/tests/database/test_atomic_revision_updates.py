"""Tests for atomic aircraft revision pointer updates."""

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import (
    AircraftRevisionError,
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
    database_path = tmp_path / "test_atomic.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"timeout": 5},
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


def test_stale_revision_rejected_across_sessions(database):
    engine, aircraft_id = database

    with Session(engine) as session:
        aircraft = session.get(AircraftProfile, aircraft_id)
        service = AircraftRevisionService(session)

        first = service.create_revision(
            aircraft,
            {"empty_weight_kg": 680},
            "Initial revision",
            expected_revision_id=None,
        )

        session.commit()
        first_id = first.id

    with Session(engine) as session_a, Session(engine) as session_b:
        aircraft_a = session_a.get(AircraftProfile, aircraft_id)
        aircraft_b = session_b.get(AircraftProfile, aircraft_id)

        service_a = AircraftRevisionService(session_a)
        service_b = AircraftRevisionService(session_b)

        service_a.create_revision(
            aircraft_a,
            {"empty_weight_kg": 683},
            "Updated equipment",
            expected_revision_id=first_id,
        )

        session_a.commit()

        with pytest.raises(
            AircraftRevisionError,
            match="changed since",
        ):
            service_b.create_revision(
                aircraft_b,
                {"empty_weight_kg": 685},
                "Outdated update",
                expected_revision_id=first_id,
            )

        session_b.rollback()

    with Session(engine) as session:
        revisions = list(
            session.scalars(
                select(AircraftProfileRevision).where(
                    AircraftProfileRevision.profile_id == aircraft_id
                )
            )
        )

        aircraft = session.get(AircraftProfile, aircraft_id)

        assert len(revisions) == 2
        assert aircraft.current_revision_id != first_id


def test_initial_revision_requires_empty_current_pointer(database):
    engine, aircraft_id = database

    with Session(engine) as session:
        aircraft = session.get(AircraftProfile, aircraft_id)
        service = AircraftRevisionService(session)

        service.create_revision(
            aircraft,
            {"empty_weight_kg": 680},
            "Initial revision",
            expected_revision_id=None,
        )

        session.commit()

    with Session(engine) as session:
        aircraft = session.get(AircraftProfile, aircraft_id)
        service = AircraftRevisionService(session)

        with pytest.raises(
            AircraftRevisionError,
            match="changed since",
        ):
            service.create_revision(
                aircraft,
                {"empty_weight_kg": 685},
                "Incorrect initial revision",
                expected_revision_id=None,
            )

        session.rollback()
