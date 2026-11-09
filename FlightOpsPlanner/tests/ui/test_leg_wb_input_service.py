"""Tests for crew and fuel loading input validation."""

import pytest

from app.leg_wb_input_service import (
    LoadingInputError,
    build_leg_conditions,
    required_weight,
)


def valid_inputs():
    return {
        "leg_uid": "LEG001",
        "pilot_weight_kg": 85,
        "pilot_station_id": "PILOT",
        "takeoff_fuel": {"FUEL": 100},
        "landing_fuel": {"FUEL": 70},
    }


def test_valid_conditions():
    conditions = build_leg_conditions(**valid_inputs())

    assert conditions.crew[0].weight_kg == 85
    assert conditions.takeoff_fuel_kg == 100
    assert conditions.landing_fuel_kg == 70


def test_missing_pilot_weight_rejected():
    data = valid_inputs()
    data["pilot_weight_kg"] = None

    with pytest.raises(LoadingInputError):
        build_leg_conditions(**data)


def test_missing_pilot_station_rejected():
    data = valid_inputs()
    data["pilot_station_id"] = ""

    with pytest.raises(LoadingInputError):
        build_leg_conditions(**data)


def test_missing_takeoff_fuel_rejected():
    data = valid_inputs()
    data["takeoff_fuel"] = {"FUEL": None}

    with pytest.raises(LoadingInputError):
        build_leg_conditions(**data)


def test_missing_landing_fuel_rejected():
    data = valid_inputs()
    data["landing_fuel"] = {"FUEL": None}

    with pytest.raises(LoadingInputError):
        build_leg_conditions(**data)


def test_negative_weight_rejected():
    with pytest.raises(LoadingInputError):
        required_weight(-1, "Weight")


def test_nonfinite_weight_rejected():
    with pytest.raises(LoadingInputError):
        required_weight(float("nan"), "Weight")


def test_zero_is_not_treated_as_missing():
    assert required_weight(0, "Weight") == 0


def test_mismatched_fuel_stations_rejected():
    data = valid_inputs()
    data["landing_fuel"] = {"OTHER_FUEL": 70}

    with pytest.raises(LoadingInputError):
        build_leg_conditions(**data)


def test_multiple_fuel_stations():
    data = valid_inputs()

    data["takeoff_fuel"] = {
        "FUEL_A": 100,
        "FUEL_B": 50,
    }

    data["landing_fuel"] = {
        "FUEL_A": 80,
        "FUEL_B": 40,
    }

    conditions = build_leg_conditions(**data)

    assert conditions.takeoff_fuel_kg == 150
    assert conditions.landing_fuel_kg == 120
    assert conditions.planned_fuel_consumption_kg == 30
