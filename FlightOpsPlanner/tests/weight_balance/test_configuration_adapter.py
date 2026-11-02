"""Tests for W&B calculations from versioned aircraft configurations."""

from types import SimpleNamespace

import pytest

from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
    calculate_from_revision,
)
from flightops.weight_balance.units import MassUnit


def revision_snapshot(
    *,
    status="structurally_valid",
    include_wb=True,
):
    configuration = {
        "schema_version": 1,
        "registration": "5H-TEST",
        "serial_number": "TEST-001",
        "variant_id": "variant-001",
        "status": status,
        "technical_documents": [
            {
                "document_id": "WB-001",
                "document_type": "weight_balance",
                "title": "Test aircraft W&B data",
            }
        ],
    }

    if include_wb:
        configuration["weight_balance"] = {
            "basic_empty_weight_kg": 680,
            "basic_empty_weight_longitudinal_arm_mm": 2500,
            "datum_description": "Test aircraft datum",
            "source_document_id": "WB-001",
            "loading_stations": [
                {
                    "station_id": "pilot",
                    "description": "Pilot seat",
                    "longitudinal_arm_mm": 2000,
                    "maximum_load_kg": 120,
                },
                {
                    "station_id": "baggage",
                    "description": "Baggage compartment",
                    "longitudinal_arm_mm": 3000,
                    "maximum_load_kg": 50,
                },
            ],
        }

    return SimpleNamespace(
        id="revision-001",
        profile_id="aircraft-001",
        revision_number=1,
        snapshot=configuration,
    )


def test_empty_aircraft_calculation():
    result = calculate_from_revision(
        revision_snapshot(),
        assignments=(),
    )

    assert result.calculation.total_weight_kg == 680
    assert result.calculation.cg_mm == 2500


def test_revision_identity_preserved():
    result = calculate_from_revision(
        revision_snapshot(),
        assignments=(),
    )

    assert result.aircraft_profile_id == "aircraft-001"
    assert result.configuration_revision_id == "revision-001"
    assert result.configuration_revision_number == 1


def test_passenger_added_to_empty_aircraft():
    result = calculate_from_revision(
        revision_snapshot(),
        assignments=(
            WBLoadAssignment(
                station_id="pilot",
                name="Pilot",
                weight=80,
                weight_unit=MassUnit.KG,
            ),
        ),
    )

    assert result.calculation.total_weight_kg == 760

    expected_moment = 680 * 2500 + 80 * 2000

    assert result.calculation.total_moment_kg_mm == pytest.approx(expected_moment)


def test_pound_load_converted():
    result = calculate_from_revision(
        revision_snapshot(),
        assignments=(
            WBLoadAssignment(
                station_id="pilot",
                name="Pilot",
                weight=176.3698,
                weight_unit=MassUnit.LB,
            ),
        ),
    )

    assert result.calculation.total_weight_kg == pytest.approx(
        760,
        abs=0.01,
    )


def test_unknown_station_rejected():
    with pytest.raises(ConfigurationAdapterError):
        calculate_from_revision(
            revision_snapshot(),
            assignments=(
                WBLoadAssignment(
                    "unknown",
                    "Passenger",
                    80,
                    MassUnit.KG,
                ),
            ),
        )


def test_station_maximum_rejected():
    with pytest.raises(ConfigurationAdapterError):
        calculate_from_revision(
            revision_snapshot(),
            assignments=(
                WBLoadAssignment(
                    "baggage",
                    "Baggage",
                    60,
                    MassUnit.KG,
                ),
            ),
        )


def test_combined_station_maximum_rejected():
    with pytest.raises(ConfigurationAdapterError):
        calculate_from_revision(
            revision_snapshot(),
            assignments=(
                WBLoadAssignment(
                    "baggage",
                    "Bag A",
                    30,
                    MassUnit.KG,
                ),
                WBLoadAssignment(
                    "baggage",
                    "Bag B",
                    30,
                    MassUnit.KG,
                ),
            ),
        )


def test_draft_configuration_rejected():
    with pytest.raises(ConfigurationAdapterError):
        calculate_from_revision(
            revision_snapshot(status="draft"),
            assignments=(),
        )


def test_missing_weight_balance_rejected():
    with pytest.raises(ConfigurationAdapterError):
        calculate_from_revision(
            revision_snapshot(include_wb=False),
            assignments=(),
        )
