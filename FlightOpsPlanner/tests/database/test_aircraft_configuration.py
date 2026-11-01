"""Tests for aircraft configuration validation."""

import pytest
from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    LoadingStation,
    WeightBalanceConfiguration,
)


def test_valid_draft_configuration():
    configuration = AircraftConfiguration(
        registration="5H-TEST",
        serial_number="TEST-001",
        variant_id="r44-raven-ii",
    )

    assert configuration.registration == "5H-TEST"
    assert configuration.status == "draft"


def test_negative_empty_weight_rejected():
    with pytest.raises(ValidationError):
        WeightBalanceConfiguration(
            basic_empty_weight_kg=-100,
            basic_empty_weight_longitudinal_arm_mm=2500,
            datum_description="Example datum",
            source_document_id="wb-report-001",
        )


def test_duplicate_loading_stations_rejected():
    with pytest.raises(ValidationError):
        WeightBalanceConfiguration(
            basic_empty_weight_kg=680,
            basic_empty_weight_longitudinal_arm_mm=2500,
            datum_description="Example datum",
            source_document_id="wb-report-001",
            loading_stations=[
                LoadingStation(
                    station_id="front_left",
                    description="Front left seat",
                    longitudinal_arm_mm=1200,
                ),
                LoadingStation(
                    station_id="front_left",
                    description="Duplicate station",
                    longitudinal_arm_mm=1200,
                ),
            ],
        )


def test_missing_source_document_rejected():
    with pytest.raises(ValidationError):
        AircraftConfiguration(
            registration="5H-TEST",
            serial_number="TEST-001",
            variant_id="r44-raven-ii",
            weight_balance={
                "basic_empty_weight_kg": 680,
                "basic_empty_weight_longitudinal_arm_mm": 2500,
                "datum_description": "Example datum",
                "source_document_id": "missing-document",
            },
        )


def test_valid_weight_balance_document_reference():
    configuration = AircraftConfiguration(
        registration="5H-TEST",
        serial_number="TEST-001",
        variant_id="r44-raven-ii",
        weight_balance={
            "basic_empty_weight_kg": 680,
            "basic_empty_weight_longitudinal_arm_mm": 2500,
            "datum_description": "Example datum",
            "source_document_id": "wb-report-001",
        },
        technical_documents=[
            {
                "document_id": "wb-report-001",
                "document_type": "weight_balance_report",
                "title": "Example W&B Report",
            }
        ],
    )

    assert configuration.weight_balance is not None
    assert configuration.weight_balance.basic_empty_weight_kg == 680


def test_unknown_configuration_fields_rejected():
    with pytest.raises(ValidationError):
        AircraftConfiguration(
            registration="5H-TEST",
            serial_number="TEST-001",
            variant_id="r44-raven-ii",
            unknown_field="invalid",
        )
