"""Tests for integrated operation fuel and W&B assessments."""

import pytest

from flightops.operations.schemas.flight import FlightOperation
from flightops.operations.services.fuel_continuity import (
    FuelContinuityError,
    RefuelEvent,
    RefuelQuantity,
)
from flightops.operations.services.leg_weight_balance import (
    calculate_operation_weight_balance,
)
from tests.operations.test_leg_weight_balance import make_leg
from tests.weight_balance.test_revision_bound_validation import aircraft
from tests.weight_balance.test_zero_fuel import configured_revision


def make_operation(*, second_departure=40.0):
    configuration = configured_revision()
    aircraft_profile = aircraft()

    operation = FlightOperation(
        operation_id="FO-INTEGRATED-001",
        aircraft_profile_id=aircraft_profile.id,
        configuration_revision_id=configuration.id,
        legs=[
            make_leg(
                number=1,
                origin="HTZA",
                destination="HTDA",
                fuel_kg=60.0,
                burn_kg=20.0,
            ),
            make_leg(
                number=2,
                origin="HTDA",
                destination="HTPE",
                fuel_kg=second_departure,
                burn_kg=15.0,
            ),
        ],
    )

    return operation, configuration, aircraft_profile


def test_continuous_fuel_allows_integrated_assessment():
    operation, configuration, aircraft_profile = make_operation()

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
    )

    assert len(result.legs) == 2
    assert len(result.fuel_continuity.transitions) == 1

    transition = result.fuel_continuity.transitions[0]

    assert transition.after_leg_id == "leg-1"
    assert transition.before_leg_id == "leg-2"


def test_unexplained_fuel_increase_blocks_assessment():
    operation, configuration, aircraft_profile = make_operation(second_departure=70.0)

    with pytest.raises(
        FuelContinuityError,
        match="Fuel continuity mismatch",
    ):
        calculate_operation_weight_balance(
            operation,
            configuration,
            aircraft_profile,
        )


def test_refuelling_allows_increased_departure_fuel():
    operation, configuration, aircraft_profile = make_operation(second_departure=70.0)

    event = RefuelEvent(
        after_leg_id="leg-1",
        before_leg_id="leg-2",
        quantities=[
            RefuelQuantity(
                station_id="fuel-main",
                quantity_kg=30.0,
            )
        ],
    )

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
        refuel_events=(event,),
    )

    transition = result.fuel_continuity.transitions[0]

    assert transition.tanks[0].previous_arrival_kg == pytest.approx(40.0)
    assert transition.tanks[0].refuelled_kg == pytest.approx(30.0)
    assert transition.tanks[0].planned_departure_kg == pytest.approx(70.0)


def test_incorrect_refuelling_blocks_assessment():
    operation, configuration, aircraft_profile = make_operation(second_departure=70.0)

    event = RefuelEvent(
        after_leg_id="leg-1",
        before_leg_id="leg-2",
        quantities=[
            RefuelQuantity(
                station_id="fuel-main",
                quantity_kg=20.0,
            )
        ],
    )

    with pytest.raises(FuelContinuityError):
        calculate_operation_weight_balance(
            operation,
            configuration,
            aircraft_profile,
            refuel_events=(event,),
        )


def test_integrated_results_preserve_revision_identity():
    operation, configuration, aircraft_profile = make_operation()

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
    )

    assert result.configuration_revision_id == configuration.id

    for leg in result.legs:
        for assessment in (
            leg.zero_fuel,
            leg.departure,
            leg.arrival,
        ):
            assert assessment.validation.configuration_revision_id == configuration.id


def test_single_leg_requires_no_refuelling():
    operation, configuration, aircraft_profile = make_operation()

    operation = operation.model_copy(update={"legs": [operation.legs[0]]})

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
    )

    assert len(result.legs) == 1
    assert result.fuel_continuity.transitions == ()
