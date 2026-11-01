"""Tests for aircraft configuration and revision integration."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from flightops.aircraft.configuration_service import (
    AircraftConfigurationError,
    AircraftConfigurationService,
)
from flightops.database.base import Base
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftVariant,
    Manufacturer,
)


@pytest.fixture
def aircraft_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

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

        yield session, profile

    engine.dispose()


def valid_configuration(profile):
    return {
        "registration": profile.registration,
        "serial_number": profile.serial_number,
        "variant_id": profile.variant_id,
        "status": "draft",
    }


def test_valid_configuration_creates_revision(aircraft_session):
    session, profile = aircraft_session

    service = AircraftConfigurationService(session)

    revision = service.save_configuration(
        profile,
        valid_configuration(profile),
        "Initial aircraft configuration",
    )

    assert revision.revision_number == 1
    assert profile.current_revision_id == revision.id


def test_invalid_registration_rejected(aircraft_session):
    session, profile = aircraft_session

    configuration = valid_configuration(profile)
    configuration["registration"] = "5H-WRONG"

    service = AircraftConfigurationService(session)

    with pytest.raises(AircraftConfigurationError):
        service.save_configuration(
            profile,
            configuration,
            "Incorrect registration",
        )


def test_invalid_variant_rejected(aircraft_session):
    session, profile = aircraft_session

    configuration = valid_configuration(profile)
    configuration["variant_id"] = "wrong-variant"

    service = AircraftConfigurationService(session)

    with pytest.raises(AircraftConfigurationError):
        service.save_configuration(
            profile,
            configuration,
            "Incorrect variant",
        )


def test_operational_verification_rejected(aircraft_session):
    session, profile = aircraft_session

    configuration = valid_configuration(profile)
    configuration["status"] = "operationally_verified"

    service = AircraftConfigurationService(session)

    with pytest.raises(AircraftConfigurationError):
        service.save_configuration(
            profile,
            configuration,
            "Attempted operational verification",
        )


def test_current_configuration_retrieval(aircraft_session):
    session, profile = aircraft_session

    service = AircraftConfigurationService(session)

    service.save_configuration(
        profile,
        valid_configuration(profile),
        "Initial aircraft configuration",
    )

    current = service.get_current_configuration(profile)

    assert current is not None
    assert current.registration == "5H-TEST"
    assert current.status == "draft"
