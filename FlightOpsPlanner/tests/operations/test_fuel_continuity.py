"""Tests for fuel continuity across flight-operation legs."""

import pytest
from pydantic import ValidationError

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
)
from flightops.operations.services.fuel_continuity import (
    FuelContinuityError,
    RefuelEvent,
    RefuelQuantity,
    validate_fuel_continuity,
)


def make_leg(number, origin, destination, departure, burn):
    return FlightLeg(
        leg_id=f"leg-{number}",
        sequence_number=number,
        departure=FlightLocation(
            location_id=origin,
            name=origin,
        ),
        destination=FlightLocation(
            location_id=destination,
            name=destination,
        ),
        fuel=LegFuelState(
            tanks=[
                LegFuelTank(
                    station_id="main",
                    departure_fuel_kg=departure,
                    planned_burn_kg=burn,
                )
            ]
        ),
    )


def operation(second_departure=75.0):
    return FlightOperation(
        operation_id="FO-001",
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        legs=[
            make_leg(1, "HTZA", "HTDA", 100, 25),
            make_leg(2, "HTDA", "HTPE", second_departure, 20),
        ],
    )


def refuel(quantity):
    return RefuelEvent(
        after_leg_id="leg-1",
        before_leg_id="leg-2",
        quantities=[
            RefuelQuantity(
                station_id="main",
                quantity_kg=quantity,
            )
        ],
    )


def test_continuous_fuel_without_refuelling():
    result = validate_fuel_continuity(operation())

    assert len(result.transitions) == 1
    assert result.transitions[0].tanks[0].expected_departure_kg == 75


def test_refuelling_increases_next_departure_fuel():
    result = validate_fuel_continuity(
        operation(second_departure=105),
        (refuel(30),),
    )

    tank = result.transitions[0].tanks[0]

    assert tank.previous_arrival_kg == 75
    assert tank.refuelled_kg == 30
    assert tank.expected_departure_kg == 105


def test_unexplained_fuel_increase_rejected():
    with pytest.raises(
        FuelContinuityError,
        match="Fuel continuity mismatch",
    ):
        validate_fuel_continuity(operation(second_departure=105))


def test_unexplained_fuel_decrease_rejected():
    with pytest.raises(
        FuelContinuityError,
        match="Fuel continuity mismatch",
    ):
        validate_fuel_continuity(operation(second_departure=65))


def test_incorrect_refuelling_quantity_rejected():
    with pytest.raises(FuelContinuityError):
        validate_fuel_continuity(
            operation(second_departure=105),
            (refuel(20),),
        )


def test_negative_refuelling_rejected():
    with pytest.raises(ValidationError):
        refuel(-10)


def test_zero_refuelling_quantity_rejected():
    with pytest.raises(ValidationError):
        refuel(0)


def test_duplicate_refuelling_tank_rejected():
    with pytest.raises(ValidationError, match="must be unique"):
        RefuelEvent(
            after_leg_id="leg-1",
            before_leg_id="leg-2",
            quantities=[
                RefuelQuantity(station_id="main", quantity_kg=10),
                RefuelQuantity(station_id="main", quantity_kg=20),
            ],
        )


def test_duplicate_refuelling_event_rejected():
    with pytest.raises(
        FuelContinuityError,
        match="Duplicate refuelling event",
    ):
        validate_fuel_continuity(
            operation(second_departure=105),
            (refuel(30), refuel(30)),
        )


def test_unknown_refuelling_station_rejected():
    event = RefuelEvent(
        after_leg_id="leg-1",
        before_leg_id="leg-2",
        quantities=[
            RefuelQuantity(
                station_id="unknown",
                quantity_kg=30,
            )
        ],
    )

    with pytest.raises(
        FuelContinuityError,
        match="unknown fuel tank",
    ):
        validate_fuel_continuity(
            operation(second_departure=105),
            (event,),
        )


def test_single_leg_requires_no_transition():
    flight = FlightOperation(
        operation_id="FO-002",
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        legs=[
            make_leg(1, "HTZA", "HTDA", 100, 25),
        ],
    )

    result = validate_fuel_continuity(flight)

    assert result.transitions == ()


def test_refuelling_references_consecutive_legs():
    event = RefuelEvent(
        after_leg_id="leg-1",
        before_leg_id="leg-99",
        quantities=[
            RefuelQuantity(
                station_id="main",
                quantity_kg=30,
            )
        ],
    )

    with pytest.raises(
        FuelContinuityError,
        match="consecutive flight legs",
    ):
        validate_fuel_continuity(
            operation(second_departure=105),
            (event,),
        )
