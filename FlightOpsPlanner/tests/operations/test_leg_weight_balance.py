"""Tests for revision-bound per-leg W&B calculations."""

from copy import deepcopy
from math import isclose

import pytest

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
    LegLoadAssignment,
    LegLoadCategory,
)
from flightops.operations.services.leg_weight_balance import (
    calculate_leg_weight_balance,
    calculate_operation_weight_balance,
)
from flightops.weight_balance.configuration_adapter import ConfigurationAdapterError
from flightops.weight_balance.validation import WBValidationStatus
from tests.weight_balance.test_revision_bound_validation import aircraft
from tests.weight_balance.test_zero_fuel import configured_revision


def location(code):
    return FlightLocation(location_id=code, name=code)


def make_leg(
    number=1,
    origin="HTZA",
    destination="HTDA",
    fuel_kg=60.0,
    burn_kg=20.0,
    baggage_kg=0.0,
):
    loads = []

    if baggage_kg:
        loads.append(
            LegLoadAssignment(
                assignment_id=f"baggage-{number}",
                station_id="test-baggage",
                name="Baggage",
                category=LegLoadCategory.BAGGAGE,
                weight_kg=baggage_kg,
            )
        )

    return FlightLeg(
        leg_id=f"leg-{number}",
        sequence_number=number,
        departure=location(origin),
        destination=location(destination),
        loads=loads,
        fuel=LegFuelState(
            tanks=[
                LegFuelTank(
                    station_id="fuel-main",
                    departure_fuel_kg=fuel_kg,
                    planned_burn_kg=burn_kg,
                )
            ]
        ),
    )


def test_departure_weight_includes_fuel():
    result = calculate_leg_weight_balance(
        make_leg(fuel_kg=60, burn_kg=20),
        configured_revision(),
        aircraft(),
    )

    assert isclose(
        result.departure_weight_kg - result.zero_fuel_weight_kg,
        60.0,
    )


def test_arrival_weight_reflects_fuel_burn():
    result = calculate_leg_weight_balance(
        make_leg(fuel_kg=60, burn_kg=20),
        configured_revision(),
        aircraft(),
    )

    assert isclose(
        result.departure_weight_kg - result.arrival_weight_kg,
        20.0,
    )


def test_zero_fuel_weight_excludes_usable_fuel():
    result = calculate_leg_weight_balance(
        make_leg(fuel_kg=100, burn_kg=40),
        configured_revision(),
        aircraft(),
    )

    assert result.zero_fuel_weight_kg < result.arrival_weight_kg
    assert result.arrival_weight_kg < result.departure_weight_kg


def test_baggage_changes_all_loading_conditions():
    configuration = configured_revision()

    empty = calculate_leg_weight_balance(
        make_leg(baggage_kg=0),
        configuration,
        aircraft(),
    )

    loaded = calculate_leg_weight_balance(
        make_leg(baggage_kg=25),
        configuration,
        aircraft(),
    )

    assert isclose(
        loaded.zero_fuel_weight_kg - empty.zero_fuel_weight_kg,
        25.0,
    )

    assert isclose(
        loaded.departure_weight_kg - empty.departure_weight_kg,
        25.0,
    )

    assert isclose(
        loaded.arrival_weight_kg - empty.arrival_weight_kg,
        25.0,
    )


def test_departure_and_arrival_use_different_weight_checks():
    from flightops.weight_balance.validation import WBWeightCheck

    result = calculate_leg_weight_balance(
        make_leg(),
        configured_revision(),
        aircraft(),
    )

    assert result.departure.validation.weight_check == WBWeightCheck.TAKEOFF
    assert result.arrival.validation.weight_check == WBWeightCheck.LANDING


def test_multiple_legs_have_independent_loading():
    configuration = configured_revision()
    aircraft_profile = aircraft()

    operation = FlightOperation(
        operation_id="FO-001",
        aircraft_profile_id=aircraft_profile.id,
        configuration_revision_id=configuration.id,
        legs=[
            make_leg(
                number=1,
                origin="HTZA",
                destination="HTDA",
                baggage_kg=25,
            ),
            make_leg(
                number=2,
                origin="HTDA",
                destination="HTPE",
                fuel_kg=40,
                baggage_kg=0,
            ),
        ],
    )

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
    )

    assert len(result.legs) == 2

    assert isclose(
        result.legs[0].zero_fuel_weight_kg - result.legs[1].zero_fuel_weight_kg,
        25.0,
    )


def test_wrong_configuration_revision_rejected():
    configuration = configured_revision()
    aircraft_profile = aircraft()

    operation = FlightOperation(
        operation_id="FO-001",
        aircraft_profile_id=aircraft_profile.id,
        configuration_revision_id="incorrect-revision",
        legs=[make_leg()],
    )

    with pytest.raises(
        ConfigurationAdapterError,
        match="different configuration revision",
    ):
        calculate_operation_weight_balance(
            operation,
            configuration,
            aircraft_profile,
        )


def test_unknown_fuel_station_rejected():
    leg = make_leg()
    leg.fuel.tanks[0].station_id = "unknown-fuel"

    with pytest.raises(ConfigurationAdapterError, match="Unknown fuel station"):
        calculate_leg_weight_balance(
            leg,
            configured_revision(),
            aircraft(),
        )


def test_non_fuel_load_cannot_use_fuel_station():
    leg = make_leg()
    leg.loads.append(
        LegLoadAssignment(
            assignment_id="invalid-load",
            station_id="fuel-main",
            name="Baggage",
            category=LegLoadCategory.BAGGAGE,
            weight_kg=10.0,
        )
    )

    with pytest.raises(ConfigurationAdapterError, match="Non-fuel load"):
        calculate_leg_weight_balance(
            leg,
            configured_revision(),
            aircraft(),
        )


def test_multiple_fuel_tanks_calculated_independently():
    leg = make_leg(
        fuel_kg=60.0,
        burn_kg=20.0,
    )

    leg.fuel.tanks.append(
        LegFuelTank(
            station_id="fuel-aux",
            departure_fuel_kg=40.0,
            planned_burn_kg=10.0,
        )
    )

    result = calculate_leg_weight_balance(
        leg,
        configured_revision(),
        aircraft(),
    )

    assert isclose(
        result.departure_weight_kg - result.zero_fuel_weight_kg,
        100.0,
    )

    assert isclose(
        result.arrival_weight_kg - result.zero_fuel_weight_kg,
        70.0,
    )

    assert isclose(
        result.departure_weight_kg - result.arrival_weight_kg,
        30.0,
    )


def test_fuel_distribution_affects_cg():
    main_fuel = calculate_leg_weight_balance(
        make_leg(
            fuel_kg=60.0,
            burn_kg=0.0,
        ),
        configured_revision(),
        aircraft(),
    )

    auxiliary_leg = make_leg(
        fuel_kg=0.0,
        burn_kg=0.0,
    )

    auxiliary_leg.fuel.tanks.append(
        LegFuelTank(
            station_id="fuel-aux",
            departure_fuel_kg=60.0,
            planned_burn_kg=0.0,
        )
    )

    auxiliary_fuel = calculate_leg_weight_balance(
        auxiliary_leg,
        configured_revision(),
        aircraft(),
    )

    assert isclose(
        main_fuel.departure_weight_kg,
        auxiliary_fuel.departure_weight_kg,
    )

    assert not isclose(
        main_fuel.departure.validation.cg_mm,
        auxiliary_fuel.departure.validation.cg_mm,
    )


def passenger_revision():
    configuration = deepcopy(configured_revision())

    configuration.snapshot["weight_balance"]["loading_stations"].append(
        {
            "station_id": "rear-passenger",
            "description": "Rear passenger seating",
            "category": "passenger",
            "longitudinal_arm_mm": 2550.0,
        }
    )

    return configuration


def test_passenger_disembarking_changes_next_leg_weight():
    configuration = passenger_revision()
    aircraft_profile = aircraft()

    first_leg = make_leg(
        number=1,
        origin="HTZA",
        destination="HTDA",
    )

    first_leg.loads.append(
        LegLoadAssignment(
            assignment_id="passenger-001",
            station_id="rear-passenger",
            name="Passenger A",
            category=LegLoadCategory.PASSENGER,
            person_id="person-001",
            weight_kg=80.0,
        )
    )

    second_leg = make_leg(
        number=2,
        origin="HTDA",
        destination="HTPE",
        fuel_kg=40.0,
    )

    operation = FlightOperation(
        operation_id="FO-002",
        aircraft_profile_id=aircraft_profile.id,
        configuration_revision_id=configuration.id,
        legs=[first_leg, second_leg],
    )

    result = calculate_operation_weight_balance(
        operation,
        configuration,
        aircraft_profile,
    )

    assert isclose(
        result.legs[0].zero_fuel_weight_kg - result.legs[1].zero_fuel_weight_kg,
        80.0,
    )

    assert (
        result.legs[0].zero_fuel.validation.cg_mm
        != result.legs[1].zero_fuel.validation.cg_mm
    )


def test_passenger_cannot_use_baggage_station():
    leg = make_leg()

    leg.loads.append(
        LegLoadAssignment(
            assignment_id="passenger-002",
            station_id="test-baggage",
            name="Passenger B",
            category=LegLoadCategory.PASSENGER,
            person_id="person-002",
            weight_kg=75.0,
        )
    )

    with pytest.raises(
        ConfigurationAdapterError,
        match="Incompatible loading station category",
    ):
        calculate_leg_weight_balance(
            leg,
            configured_revision(),
            aircraft(),
        )


def test_fuel_cannot_use_baggage_station():
    leg = make_leg()

    leg.fuel.tanks[0].station_id = "test-baggage"

    with pytest.raises(
        ConfigurationAdapterError,
        match="not classified as usable fuel",
    ):
        calculate_leg_weight_balance(
            leg,
            configured_revision(),
            aircraft(),
        )


def test_unreviewed_fuel_classification_rejected():
    configuration = configured_revision()

    configuration.snapshot["weight_balance"]["usable_fuel_classification_reviewed"] = (
        False
    )

    with pytest.raises(
        ConfigurationAdapterError,
        match="classifications have not been reviewed",
    ):
        calculate_leg_weight_balance(
            make_leg(),
            configuration,
            aircraft(),
        )


def test_overweight_loading_returns_failed_assessment():
    leg = make_leg(
        fuel_kg=60.0,
        burn_kg=20.0,
        baggage_kg=1000.0,
    )

    result = calculate_leg_weight_balance(
        leg,
        configured_revision(),
        aircraft(),
    )

    assert result.departure.validation.status == WBValidationStatus.FAIL

    assert not result.departure.passed
