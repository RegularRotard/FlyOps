"""Tests for multi-leg flight operation models."""

import pytest
from pydantic import ValidationError

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
    LegLoadAssignment,
    LegLoadCategory,
)


def location(code):
    return FlightLocation(
        location_id=code,
        name=code,
    )


def passenger(person_id, assignment_id=None):
    return LegLoadAssignment(
        assignment_id=assignment_id or person_id,
        station_id="rear-seat",
        name=person_id,
        category=LegLoadCategory.PASSENGER,
        person_id=person_id,
        weight_kg=75.0,
    )


def fuel(departure=100.0, burn=25.0):
    return LegFuelState(
        tanks=[
            LegFuelTank(
                station_id="main-fuel",
                departure_fuel_kg=departure,
                planned_burn_kg=burn,
            )
        ]
    )


def leg(number, origin, destination, passengers=()):
    return FlightLeg(
        leg_id=f"leg-{number}",
        sequence_number=number,
        departure=location(origin),
        destination=location(destination),
        loads=list(passengers),
        fuel=fuel(),
    )


def operation(legs):
    return FlightOperation(
        operation_id="FO-001",
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        legs=legs,
    )


def test_single_leg_operation():
    result = operation(
        [
            leg(1, "HTZA", "HTDA"),
        ]
    )

    assert len(result.legs) == 1


def test_multiple_legs():
    result = operation(
        [
            leg(1, "HTZA", "HTDA"),
            leg(2, "HTDA", "HTPE"),
            leg(3, "HTPE", "HTZA"),
        ]
    )

    assert len(result.legs) == 3


def test_passenger_can_travel_on_multiple_legs():
    result = operation(
        [
            leg(1, "HTZA", "HTDA", [passenger("person-1")]),
            leg(2, "HTDA", "HTPE", [passenger("person-1")]),
        ]
    )

    assert result.legs[0].loads[0].person_id == "person-1"
    assert result.legs[1].loads[0].person_id == "person-1"


def test_passenger_not_automatically_carried_to_next_leg():
    result = operation(
        [
            leg(1, "HTZA", "HTDA", [passenger("person-1")]),
            leg(2, "HTDA", "HTPE"),
        ]
    )

    assert len(result.legs[0].loads) == 1
    assert result.legs[1].loads == []


def test_duplicate_person_on_same_leg_rejected():
    with pytest.raises(ValidationError, match="person cannot"):
        leg(
            1,
            "HTZA",
            "HTDA",
            [
                passenger("person-1", "assignment-1"),
                passenger("person-1", "assignment-2"),
            ],
        )


def test_duplicate_load_assignment_rejected():
    with pytest.raises(ValidationError, match="assignment IDs"):
        leg(
            1,
            "HTZA",
            "HTDA",
            [
                passenger("person-1", "duplicate"),
                passenger("person-2", "duplicate"),
            ],
        )


def test_passenger_requires_person_id():
    with pytest.raises(ValidationError, match="person ID"):
        LegLoadAssignment(
            assignment_id="assignment-1",
            station_id="rear-seat",
            name="Passenger",
            category=LegLoadCategory.PASSENGER,
            weight_kg=75.0,
        )


def test_fuel_burn_calculates_arrival_fuel():
    result = fuel(
        departure=120.0,
        burn=35.0,
    )

    assert result.arrival_fuel_kg == pytest.approx(85.0)


def test_multiple_tank_fuel_totals():
    result = LegFuelState(
        tanks=[
            LegFuelTank(
                station_id="main",
                departure_fuel_kg=80.0,
                planned_burn_kg=20.0,
            ),
            LegFuelTank(
                station_id="aux",
                departure_fuel_kg=40.0,
                planned_burn_kg=10.0,
            ),
        ]
    )

    assert result.departure_fuel_kg == pytest.approx(120.0)
    assert result.planned_burn_kg == pytest.approx(30.0)
    assert result.arrival_fuel_kg == pytest.approx(90.0)


def test_fuel_burn_cannot_exceed_departure_fuel():
    with pytest.raises(ValidationError, match="exceeds departure fuel"):
        fuel(
            departure=20.0,
            burn=25.0,
        )


def test_negative_fuel_rejected():
    with pytest.raises(ValidationError):
        fuel(
            departure=-10.0,
            burn=0.0,
        )


def test_duplicate_fuel_stations_rejected():
    with pytest.raises(ValidationError, match="must be unique"):
        LegFuelState(
            tanks=[
                LegFuelTank(
                    station_id="main",
                    departure_fuel_kg=50.0,
                    planned_burn_kg=10.0,
                ),
                LegFuelTank(
                    station_id="main",
                    departure_fuel_kg=20.0,
                    planned_burn_kg=5.0,
                ),
            ]
        )


def test_same_departure_and_destination_rejected():
    with pytest.raises(ValidationError, match="must be different"):
        leg(1, "HTZA", "HTZA")


def test_nonsequential_legs_rejected():
    with pytest.raises(ValidationError, match="ordered sequentially"):
        operation(
            [
                leg(1, "HTZA", "HTDA"),
                leg(3, "HTDA", "HTPE"),
            ]
        )


def test_disconnected_flight_legs_rejected():
    with pytest.raises(ValidationError, match="matching arrival"):
        operation(
            [
                leg(1, "HTZA", "HTDA"),
                leg(2, "HTPE", "HTZA"),
            ]
        )


def test_duplicate_leg_ids_rejected():
    first = leg(1, "HTZA", "HTDA")
    second = leg(2, "HTDA", "HTPE")
    second.leg_id = first.leg_id

    with pytest.raises(ValidationError, match="Flight leg IDs"):
        operation([first, second])


def test_empty_operation_rejected():
    with pytest.raises(ValidationError):
        operation([])


def test_non_finite_loading_weight_rejected():
    with pytest.raises(ValidationError):
        LegLoadAssignment(
            assignment_id="load-1",
            station_id="rear-seat",
            name="Passenger",
            category=LegLoadCategory.PASSENGER,
            person_id="person-1",
            weight_kg=float("nan"),
        )
