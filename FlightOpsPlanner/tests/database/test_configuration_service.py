"""Tests for aircraft configuration service validation."""

import pytest
from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    validate_aircraft_configuration,
)


def test_valid_configuration_accepted():
    configuration = {
        "registration": "5H-TEST",
        "serial_number": "TEST-001",
        "variant_id": "r44-raven-ii",
    }

    result = validate_aircraft_configuration(configuration)

    assert result.registration == "5H-TEST"


def test_invalid_configuration_rejected():
    configuration = {
        "registration": "",
        "serial_number": "TEST-001",
        "variant_id": "r44-raven-ii",
    }

    with pytest.raises(ValidationError):
        validate_aircraft_configuration(configuration)


def test_operational_verification_cannot_be_self_assigned():
    configuration = {
        "registration": "5H-TEST",
        "serial_number": "TEST-001",
        "variant_id": "r44-raven-ii",
        "status": "operationally_verified",
    }

    with pytest.raises(ValueError):
        validate_aircraft_configuration(configuration)
