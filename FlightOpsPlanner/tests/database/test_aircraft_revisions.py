import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import (
    AircraftRevisionError,
    AircraftRevisionService,
)
from flightops.database.base import Base
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftVariant,
    Manufacturer,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def aircraft(session):
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
        registration="5H-ABC",
        serial_number="TEST-001",
    )

    session.add(profile)
    session.flush()

    return profile


def test_create_initial_revision(session, aircraft):
    service = AircraftRevisionService(session)

    revision = service.create_revision(
        aircraft,
        {
            "empty_weight_kg": 680,
            "empty_weight_arm_mm": 2500,
        },
        "Initial configuration",
    )

    assert revision.revision_number == 1
    assert aircraft.current_revision_id == revision.id
    assert revision.snapshot["empty_weight_kg"] == 680


def test_create_second_revision(session, aircraft):
    service = AircraftRevisionService(session)

    service.create_revision(
        aircraft,
        {"empty_weight_kg": 680},
        "Initial configuration",
    )

    revision = service.create_revision(
        aircraft,
        {"empty_weight_kg": 683},
        "Equipment installed",
    )

    assert revision.revision_number == 2

    changes = revision.changes

    assert len(changes) == 1
    assert changes[0].field_path == "empty_weight_kg"
    assert changes[0].old_value == 680
    assert changes[0].new_value == 683


def test_restore_previous_revision(session, aircraft):
    service = AircraftRevisionService(session)

    service.create_revision(
        aircraft,
        {"empty_weight_kg": 680},
        "Initial configuration",
    )

    service.create_revision(
        aircraft,
        {"empty_weight_kg": 683},
        "Equipment installed",
    )

    restored = service.restore_revision(
        aircraft,
        revision_number=1,
    )

    assert restored.revision_number == 3
    assert restored.snapshot["empty_weight_kg"] == 680

    history = service.get_history(aircraft.id)

    assert len(history) == 3
    assert history[1].snapshot["empty_weight_kg"] == 683


def test_duplicate_revision_rejected(session, aircraft):
    service = AircraftRevisionService(session)

    service.create_revision(
        aircraft,
        {"empty_weight_kg": 680},
        "Initial configuration",
    )

    with pytest.raises(AircraftRevisionError):
        service.create_revision(
            aircraft,
            {"empty_weight_kg": 680},
            "No actual change",
        )


def test_nested_configuration_changes():
    changes = AircraftRevisionService.compare_snapshots(
        {
            "engine": {
                "model": "Example A",
                "serial": "123",
            }
        },
        {
            "engine": {
                "model": "Example B",
                "serial": "123",
            }
        },
    )

    assert len(changes) == 1
    assert changes[0]["field_path"] == "engine.model"
def test_outdated_revision_rejected(session, aircraft):
    service = AircraftRevisionService(session)

    first = service.create_revision(
        aircraft,
        {"empty_weight_kg": 680},
        "Initial configuration",
    )

    service.create_revision(
        aircraft,
        {"empty_weight_kg": 683},
        "Equipment installed",
        expected_revision_id=first.id,
    )

    with pytest.raises(AircraftRevisionError, match="changed since"):
        service.create_revision(
            aircraft,
            {"empty_weight_kg": 685},
            "Outdated configuration",
            expected_revision_id=first.id,
        )

    assert len(service.get_history(aircraft.id)) == 2
