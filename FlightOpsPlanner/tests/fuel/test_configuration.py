"""Tests for simplified flight and idle fuel configuration."""

import pytest
from pydantic import ValidationError

from flightops.fuel.configuration import (
    FuelConsumptionRate,
    FuelPhase,
    FuelPlanningConfiguration,
)


def sample_configuration():
    return FuelPlanningConfiguration(
        fuel_type="Fictional test fuel",
        default_density_kg_per_litre=0.8,
        density_source_document_id="density-document",
        consumption_rates=[
            FuelConsumptionRate(
                phase=FuelPhase.FLIGHT,
                consumption_kg_per_hour=72.0,
                source_document_id="performance-document",
            ),
            FuelConsumptionRate(
                phase=FuelPhase.IDLE,
                consumption_kg_per_hour=24.0,
                source_document_id="performance-document",
            ),
        ],
    )


def test_valid_configuration():
    configuration = sample_configuration()

    assert configuration.fuel_type == "Fictional test fuel"


def test_flight_rate_lookup():
    configuration = sample_configuration()

    assert (
        configuration.rate_for_phase(FuelPhase.FLIGHT).consumption_kg_per_hour == 72.0
    )


def test_idle_rate_lookup():
    configuration = sample_configuration()

    assert configuration.rate_for_phase(FuelPhase.IDLE).consumption_kg_per_hour == 24.0


def test_duplicate_flight_rates_rejected():
    data = sample_configuration().model_dump()

    data["consumption_rates"][1]["phase"] = "flight"

    with pytest.raises(ValidationError):
        FuelPlanningConfiguration.model_validate(data)


def test_missing_idle_rate_rejected():
    data = sample_configuration().model_dump()

    data["consumption_rates"] = data["consumption_rates"][:1]

    with pytest.raises(ValidationError):
        FuelPlanningConfiguration.model_validate(data)


def test_negative_density_rejected():
    data = sample_configuration().model_dump()
    data["default_density_kg_per_litre"] = -0.8

    with pytest.raises(ValidationError):
        FuelPlanningConfiguration.model_validate(data)


def test_zero_consumption_rejected():
    with pytest.raises(ValidationError):
        FuelConsumptionRate(
            phase=FuelPhase.FLIGHT,
            consumption_kg_per_hour=0,
            source_document_id="performance-document",
        )


def test_nonfinite_rate_rejected():
    with pytest.raises(ValidationError):
        FuelConsumptionRate(
            phase=FuelPhase.IDLE,
            consumption_kg_per_hour=float("inf"),
            source_document_id="performance-document",
        )


def test_missing_source_rejected():
    with pytest.raises(ValidationError):
        FuelConsumptionRate(
            phase=FuelPhase.FLIGHT,
            consumption_kg_per_hour=72,
            source_document_id="",
        )


def test_unsupported_phase_rejected():
    with pytest.raises(ValidationError):
        FuelConsumptionRate(
            phase="hover",
            consumption_kg_per_hour=72,
            source_document_id="performance-document",
        )


def test_serialisation_round_trip():
    original = sample_configuration()

    restored = FuelPlanningConfiguration.model_validate_json(original.model_dump_json())

    assert restored == original
