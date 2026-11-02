"""Tests for revision-bound automatic zero-fuel calculations."""

from copy import deepcopy
from math import isclose

import pytest

from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
)
from flightops.weight_balance.plot_service import (
    build_fuel_loading_plot_from_revision,
)
from flightops.weight_balance.units import MassUnit
from flightops.weight_balance.zero_fuel import (
    calculate_zero_fuel_from_revision,
)
from tests.weight_balance.test_revision_bound_validation import aircraft, revision


def configured_revision():
    """Create a reviewed fictional aircraft configuration."""

    result = deepcopy(revision())

    wb = result.snapshot["weight_balance"]

    wb["usable_fuel_classification_reviewed"] = True

    wb["loading_stations"].extend(
        [
            {
                "station_id": "fuel-main",
                "description": "Main usable fuel",
                "category": "usable_fuel",
                "longitudinal_arm_mm": 2400.0,
            },
            {
                "station_id": "fuel-aux",
                "description": "Auxiliary usable fuel",
                "category": "usable_fuel",
                "longitudinal_arm_mm": 2700.0,
            },
            {
                "station_id": "test-baggage",
                "description": "Baggage compartment",
                "category": "baggage",
                "longitudinal_arm_mm": 2600.0,
            },
        ]
    )

    return result


def assignment(station_id, weight):
    return WBLoadAssignment(
        station_id=station_id,
        name=station_id,
        weight=weight,
        weight_unit=MassUnit.KG,
    )


def test_unreviewed_fuel_classification_rejected():
    configuration = configured_revision()

    configuration.snapshot["weight_balance"]["usable_fuel_classification_reviewed"] = (
        False
    )

    with pytest.raises(
        ConfigurationAdapterError,
        match="classifications have not",
    ):
        calculate_zero_fuel_from_revision(
            configuration,
            (),
            aircraft(),
        )


def test_missing_fuel_station_rejected():
    configuration = configured_revision()

    wb = configuration.snapshot["weight_balance"]

    wb["loading_stations"] = [
        station
        for station in wb["loading_stations"]
        if station.get("category") != "usable_fuel"
    ]

    with pytest.raises(
        ConfigurationAdapterError,
        match="no explicitly",
    ):
        calculate_zero_fuel_from_revision(
            configuration,
            (),
            aircraft(),
        )


def test_zero_fuel_equals_takeoff_without_usable_fuel():
    assessment = calculate_zero_fuel_from_revision(
        configured_revision(),
        (),
        aircraft(),
    )

    assert isclose(
        assessment.zero_fuel.validation.total_weight_kg,
        assessment.takeoff.validation.total_weight_kg,
    )

    assert isclose(
        assessment.usable_fuel_weight_kg,
        0.0,
        abs_tol=1e-9,
    )


def test_single_fuel_tank_excluded_from_zfw():
    assessment = calculate_zero_fuel_from_revision(
        configured_revision(),
        (assignment("fuel-main", 40.0),),
        aircraft(),
    )

    assert isclose(
        assessment.usable_fuel_weight_kg,
        40.0,
    )


def test_multiple_fuel_tanks_excluded_from_zfw():
    assessment = calculate_zero_fuel_from_revision(
        configured_revision(),
        (
            assignment("fuel-main", 40.0),
            assignment("fuel-aux", 30.0),
        ),
        aircraft(),
    )

    assert isclose(
        assessment.usable_fuel_weight_kg,
        70.0,
    )


def test_baggage_remains_in_zero_fuel_weight():
    without_baggage = calculate_zero_fuel_from_revision(
        configured_revision(),
        (),
        aircraft(),
    )

    with_baggage = calculate_zero_fuel_from_revision(
        configured_revision(),
        (assignment("test-baggage", 25.0),),
        aircraft(),
    )

    difference = (
        with_baggage.zero_fuel.validation.total_weight_kg
        - without_baggage.zero_fuel.validation.total_weight_kg
    )

    assert isclose(difference, 25.0)


def test_different_fuel_arms_affect_takeoff_cg():
    main_tank = calculate_zero_fuel_from_revision(
        configured_revision(),
        (assignment("fuel-main", 40.0),),
        aircraft(),
    )

    auxiliary_tank = calculate_zero_fuel_from_revision(
        configured_revision(),
        (assignment("fuel-aux", 40.0),),
        aircraft(),
    )

    assert not isclose(
        main_tank.takeoff.validation.cg_mm,
        auxiliary_tank.takeoff.validation.cg_mm,
    )

    assert isclose(
        main_tank.zero_fuel.validation.cg_mm,
        auxiliary_tank.zero_fuel.validation.cg_mm,
    )


def test_both_conditions_preserve_revision_identity():
    configuration = configured_revision()

    assessment = calculate_zero_fuel_from_revision(
        configuration,
        (assignment("fuel-main", 30.0),),
        aircraft(),
    )

    assert assessment.takeoff.validation.configuration_revision_id == configuration.id

    assert assessment.zero_fuel.validation.configuration_revision_id == configuration.id


def test_wrong_aircraft_rejected():
    incorrect_aircraft = aircraft()
    incorrect_aircraft.id = "incorrect-aircraft"

    with pytest.raises(ConfigurationAdapterError):
        calculate_zero_fuel_from_revision(
            configured_revision(),
            (),
            incorrect_aircraft,
        )


def test_unknown_station_rejected():
    with pytest.raises(
        ConfigurationAdapterError,
        match="Unknown aircraft loading station",
    ):
        calculate_zero_fuel_from_revision(
            configured_revision(),
            (assignment("nonexistent", 20.0),),
            aircraft(),
        )


def test_automatic_zfw_graph_integration():
    configuration = configured_revision()

    assignments = (
        assignment("fuel-main", 40.0),
        assignment("fuel-aux", 30.0),
        assignment("test-baggage", 25.0),
    )

    plot = build_fuel_loading_plot_from_revision(
        configuration,
        assignments,
        aircraft(),
    )

    assert plot.zero_fuel_point is not None
    assert plot.zero_fuel_assessment is not None

    assert isclose(
        plot.zero_fuel_point.weight_kg,
        plot.zero_fuel_assessment.point.weight_kg,
    )

    assert isclose(
        plot.zero_fuel_point.cg_mm,
        plot.zero_fuel_assessment.point.cg_mm,
    )

    assert plot.configuration_revision_id == configuration.id

    assert len(plot.loading_points) == 1
    assert plot.loading_points[0].label == "Takeoff"
