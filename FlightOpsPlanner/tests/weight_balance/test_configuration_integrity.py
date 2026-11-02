"""Validation tests for aircraft W&B configuration integrity."""

import pytest
from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    LoadingStation,
    WeightBalanceConfiguration,
)
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
)
from flightops.weight_balance.units import MassUnit


def test_matching_station_longitudinal_arm():
    station = LoadingStation(
        station_id="pilot",
        description="Pilot seat",
        longitudinal_arm_mm=2540,
        longitudinal_arm={
            "value": 100,
            "unit": "in",
        },
    )

    assert station.longitudinal_arm_mm == 2540


def test_conflicting_station_longitudinal_arm():
    with pytest.raises(ValidationError):
        LoadingStation(
            station_id="pilot",
            description="Pilot seat",
            longitudinal_arm_mm=2500,
            longitudinal_arm={
                "value": 100,
                "unit": "in",
            },
        )


def test_matching_station_lateral_arm():
    station = LoadingStation(
        station_id="pilot",
        description="Pilot seat",
        longitudinal_arm_mm=2500,
        lateral_arm_mm=-254,
        lateral_arm={
            "value": -10,
            "unit": "in",
        },
    )

    assert station.lateral_arm_mm == -254


def test_missing_normalized_lateral_arm():
    with pytest.raises(ValidationError):
        LoadingStation(
            station_id="pilot",
            description="Pilot seat",
            longitudinal_arm_mm=2500,
            lateral_arm={
                "value": -10,
                "unit": "in",
            },
        )


def test_matching_station_maximum_load():
    station = LoadingStation(
        station_id="baggage",
        description="Baggage compartment",
        longitudinal_arm_mm=3000,
        maximum_load_kg=50,
        maximum_load={
            "value": 50,
            "unit": "kg",
        },
    )

    assert station.maximum_load_kg == 50


def test_conflicting_station_maximum_load():
    with pytest.raises(ValidationError):
        LoadingStation(
            station_id="baggage",
            description="Baggage compartment",
            longitudinal_arm_mm=3000,
            maximum_load_kg=50,
            maximum_load={
                "value": 100,
                "unit": "kg",
            },
        )


def test_matching_empty_aircraft_lateral_arm():
    config = WeightBalanceConfiguration(
        basic_empty_weight_kg=680,
        basic_empty_weight_longitudinal_arm_mm=2500,
        basic_empty_weight_lateral_arm_mm=-254,
        basic_empty_weight_lateral_arm={
            "value": -10,
            "unit": "in",
        },
        datum_description="Test datum",
        source_document_id="WB-001",
    )

    assert config.basic_empty_weight_lateral_arm_mm == -254


def test_conflicting_empty_aircraft_lateral_arm():
    with pytest.raises(ValidationError):
        WeightBalanceConfiguration(
            basic_empty_weight_kg=680,
            basic_empty_weight_longitudinal_arm_mm=2500,
            basic_empty_weight_lateral_arm_mm=-250,
            basic_empty_weight_lateral_arm={
                "value": -10,
                "unit": "in",
            },
            datum_description="Test datum",
            source_document_id="WB-001",
        )


@pytest.mark.parametrize(
    "weight",
    [-1, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_assignment_weight(weight):
    with pytest.raises(ConfigurationAdapterError):
        WBLoadAssignment(
            station_id="pilot",
            name="Pilot",
            weight=weight,
            weight_unit=MassUnit.KG,
        )


def test_empty_assignment_station_rejected():
    with pytest.raises(ConfigurationAdapterError):
        WBLoadAssignment(
            station_id="",
            name="Pilot",
            weight=80,
            weight_unit=MassUnit.KG,
        )


def test_empty_assignment_name_rejected():
    with pytest.raises(ConfigurationAdapterError):
        WBLoadAssignment(
            station_id="pilot",
            name="",
            weight=80,
            weight_unit=MassUnit.KG,
        )


def test_invalid_assignment_unit_rejected():
    with pytest.raises(ConfigurationAdapterError):
        WBLoadAssignment(
            station_id="pilot",
            name="Pilot",
            weight=80,
            weight_unit="invalid",
        )
