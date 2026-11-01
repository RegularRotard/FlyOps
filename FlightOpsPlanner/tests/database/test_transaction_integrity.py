"""Tests for aircraft revision transaction integrity."""

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
    AircraftRevisionChange,
    AircraftVariant,
    Manufacturer,
)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'transaction_integrity.db'}",
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


def get_database_state(engine, aircraft_id):
    with Session(engine) as session:
        aircraft = session.get(AircraftProfile, aircraft_id)

        revisions = list(
            session.scalars(
                select(AircraftProfileRevision)
                .where(AircraftProfileRevision.profile_id == aircraft_id)
                .order_by(AircraftProfileRevision.revision_number)
            )
        )

        revision_ids = [revision.id for revision in revisions]

        changes = (
            list(
                session.scalars(
                    select(AircraftRevisionChange).where(
                        AircraftRevisionChange.revision_id.in_(
                            revision_ids
                        )
                    )
                )
            )
            if revision_ids
            else []
        )

        return {
            "current_revision_id": aircraft.current_revision_id,
            "revision_count": len(revisions),
            "change_count": len(changes),
        }


def test_successful_revision_commits_atomically(database):
    engine, aircraft_id = database

    with Session(engine) as session:
        with session.begin():
            aircraft = session.get(AircraftProfile, aircraft_id)

            revision = AircraftRevisionService(
                session
            ).create_revision(
                aircraft,
                {"empty_weight_kg": 680},
                "Initial configuration",
                expected_revision_id=None,
            )

            revision_id = revision.id

    state = get_database_state(engine, aircraft_id)

    assert state["current_revision_id"] == revision_id
    assert state["revision_count"] == 1
    assert state["change_count"] >= 1


def test_exception_rolls_back_entire_revision(database):
    engine, aircraft_id = database

    with pytest.raises(RuntimeError, match="Simulated failure"):
        with Session(engine) as session:
            with session.begin():
                aircraft = session.get(
                    AircraftProfile,
                    aircraft_id,
                )

                AircraftRevisionService(
                    session
                ).create_revision(
                    aircraft,
                    {"empty_weight_kg": 680},
                    "Initial configuration",
                    expected_revision_id=None,
                )

                raise RuntimeError("Simulated failure")

    state = get_database_state(engine, aircraft_id)

    assert state["current_revision_id"] is None
    assert state["revision_count"] == 0
    assert state["change_count"] == 0


def test_stale_save_preserves_committed_history(database):
    engine, aircraft_id = database

    with Session(engine) as session:
        with session.begin():
            aircraft = session.get(
                AircraftProfile,
                aircraft_id,
            )

            first = AircraftRevisionService(
                session
            ).create_revision(
                aircraft,
                {"empty_weight_kg": 680},
                "Initial configuration",
                expected_revision_id=None,
            )

            first_id = first.id

    with pytest.raises(
        AircraftRevisionError,
        match="changed since",
    ):
        with Session(engine) as session:
            with session.begin():
                aircraft = session.get(
                    AircraftProfile,
                    aircraft_id,
                )

                AircraftRevisionService(
                    session
                ).create_revision(
                    aircraft,
                    {"empty_weight_kg": 685},
                    "Stale configuration",
                    expected_revision_id=None,
                )

    state = get_database_state(engine, aircraft_id)

    assert state["current_revision_id"] == first_id
    assert state["revision_count"] == 1


def test_explicit_rollback_removes_uncommitted_revision(database):
    engine, aircraft_id = database

    with Session(engine) as session:
        aircraft = session.get(
            AircraftProfile,
            aircraft_id,
        )

        AircraftRevisionService(
            session
        ).create_revision(
            aircraft,
            {"empty_weight_kg": 680},
            "Uncommitted configuration",
            expected_revision_id=None,
        )

        session.rollback()

    state = get_database_state(engine, aircraft_id)

    assert state["current_revision_id"] is None
    assert state["revision_count"] == 0
    assert state["change_count"] == 0
