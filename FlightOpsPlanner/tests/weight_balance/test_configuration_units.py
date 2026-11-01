"""Tests for unit-aware aircraft W&B configuration schemas."""

import pytest
from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    ArmMeasurement,
    MassMeasurement,
    WeightBalanceConfiguration,
)
from flightops.weight_balance.units import (
    LengthUnit,
    MassUnit,
    convert_mass,
)


def base_configuration():
    return {
        "basic_empty_weight_kg": 680,
        "basic_empty_weight_longitudinal_arm_mm": 2500,
        "datum_description": "Manufacturer reference datum",
        "source_document_id": "WB-001",
    }


def test_legacy_configuration_remains_valid():
    config = WeightBalanceConfiguration.model_validate(
        base_configuration()
    )

    assert config.basic_empty_weight_kg == 680


def test_mass_measurement_preserves_units():
    measurement = MassMeasurement(
        value=1500,
        unit=MassUnit.LB,
    )

    assert measurement.value == 1500
    assert measurement.unit == MassUnit.LB


def test_arm_measurement_preserves_units():
    measurement = ArmMeasurement(
        value=100,
        unit=LengthUnit.IN,
    )

    assert measurement.unit == LengthUnit.IN


def test_matching_source_weight():
    data = base_configuration()

    data["basic_empty_weight"] = {
        "value": 680,
        "unit": "kg",
    }

    config = WeightBalanceConfiguration.model_validate(data)

    assert config.basic_empty_weight.unit == MassUnit.KG


def test_matching_pound_source_weight():
    data = base_configuration()

    pounds = convert_mass(
        680,
        MassUnit.KG,
        MassUnit.LB,
    )

    data["basic_empty_weight"] = {
        "value": pounds,
        "unit": "lb",
    }

    config = WeightBalanceConfiguration.model_validate(data)

    assert config.basic_empty_weight.unit == MassUnit.LB


def test_conflicting_source_weight_rejected():
    data = base_configuration()

    data["basic_empty_weight"] = {
        "value": 1000,
        "unit": "lb",
    }

    with pytest.raises(ValidationError):
        WeightBalanceConfiguration.model_validate(data)


def test_conflicting_source_arm_rejected():
    data = base_configuration()

    data["basic_empty_weight_longitudinal_arm"] = {
        "value": 100,
        "unit": "in",
    }

    with pytest.raises(ValidationError):
        WeightBalanceConfiguration.model_validate(data)


def test_matching_source_arm():
    data = base_configuration()

    data["basic_empty_weight_longitudinal_arm"] = {
        "value": 250,
        "unit": "cm",
    }

    config = WeightBalanceConfiguration.model_validate(data)

    assert (
        config.basic_empty_weight_longitudinal_arm.unit
        == LengthUnit.CM
    )
