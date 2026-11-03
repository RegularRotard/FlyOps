"""Tests for flight classification in the primary FlightLeg model."""

import pytest
from pydantic import ValidationError

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    LegFuelState,
)
from flightops.operations.schemas.flight_planning import FlightType


def create_leg(
    flight_type: FlightType | None,
    departure_id: str,
    destination_id: str,
) -> FlightLeg:
    return FlightLeg(
        leg_id="LEG-001",
        sequence_number=1,
        flight_type=flight_type,
        departure=FlightLocation(
            location_id=departure_id,
            name=departure_id,
        ),
        destination=FlightLocation(
            location_id=destination_id,
            name=destination_id,
        ),
        fuel=LegFuelState(tanks=[]),
    )


def test_scenic_round_trip_allowed():
    leg = create_leg(
        FlightType.SCENIC,
        "HTZA",
        "HTZA",
    )

    assert leg.departure.location_id == leg.destination.location_id


def test_scenic_different_destination_allowed():
    leg = create_leg(
        FlightType.SCENIC,
        "HTZA",
        "HTDA",
    )

    assert leg.flight_type == FlightType.SCENIC


def test_charter_round_trip_rejected():
    with pytest.raises(ValidationError, match="must be different"):
        create_leg(
            FlightType.CHARTER,
            "HTZA",
            "HTZA",
        )


def test_ferry_round_trip_rejected():
    with pytest.raises(ValidationError, match="must be different"):
        create_leg(
            FlightType.FERRY,
            "HTZA",
            "HTZA",
        )


def test_unclassified_round_trip_still_rejected():
    with pytest.raises(ValidationError, match="must be different"):
        create_leg(
            None,
            "HTZA",
            "HTZA",
        )


def test_ferry_between_locations_allowed():
    leg = create_leg(
        FlightType.FERRY,
        "HTZA",
        "HTDA",
    )

    assert leg.flight_type == FlightType.FERRY


def test_flight_type_serialisation():
    leg = create_leg(
        FlightType.SCENIC,
        "HTZA",
        "HTZA",
    )

    restored = FlightLeg.model_validate_json(leg.model_dump_json())

    assert restored == leg
