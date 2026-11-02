"""Tests for revision-bound aircraft W&B validation."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
)
from flightops.weight_balance.plot_service import build_cg_plot_from_revision
from flightops.weight_balance.revision_validation import (
    WBVerificationLevel,
    validate_from_revision,
)
from flightops.weight_balance.validation import WBValidationStatus


def aircraft():
    return SimpleNamespace(
        id="aircraft-001",
        registration="5H-TEST",
        serial_number="TEST-001",
        variant_id="variant-001",
    )


def revision(
    *,
    status="operationally_verified",
    include_limits=True,
    include_envelope=True,
    revision_number=3,
):
    """Create a fictional aircraft configuration revision."""

    wb = {
        "basic_empty_weight_kg": 900,
        "basic_empty_weight_longitudinal_arm_mm": 2500,
        "datum_description": "Fictional test datum",
        "source_document_id": "WB-TEST-001",
        "loading_stations": [],
    }

    if include_limits:
        wb["weight_limits"] = {
            "maximum_takeoff_weight_kg": 1100,
            "maximum_landing_weight_kg": 1050,
            "minimum_operating_weight_kg": 700,
        }

    if include_envelope:
        wb["longitudinal_cg_envelope"] = {
            "points": [
                {
                    "weight_kg": 700,
                    "forward_limit_mm": 2200,
                    "aft_limit_mm": 2700,
                },
                {
                    "weight_kg": 1100,
                    "forward_limit_mm": 2300,
                    "aft_limit_mm": 2600,
                },
            ]
        }

    snapshot = {
        "schema_version": 1,
        "registration": "5H-TEST",
        "serial_number": "TEST-001",
        "variant_id": "variant-001",
        "status": status,
        "weight_balance": wb,
        "technical_documents": [
            {
                "document_id": "WB-TEST-001",
                "document_type": "weight_balance",
                "title": "Fictional W&B Test Document",
            }
        ],
    }

    return SimpleNamespace(
        id="revision-003",
        profile_id="aircraft-001",
        revision_number=revision_number,
        snapshot=snapshot,
    )


def test_verified_configuration_passes():
    result = validate_from_revision(
        revision(),
        (),
        aircraft(),
    )

    assert result.verification_level == WBVerificationLevel.VERIFIED
    assert result.validation.status == WBValidationStatus.PASS
    assert result.passed


def test_structurally_valid_configuration_is_development_only():
    result = validate_from_revision(
        revision(status="structurally_valid"),
        (),
        aircraft(),
    )

    assert result.verification_level == WBVerificationLevel.DEVELOPMENT
    assert result.development_passed
    assert not result.passed


def test_draft_configuration_rejected():
    with pytest.raises(ConfigurationAdapterError):
        validate_from_revision(
            revision(status="draft"),
            (),
            aircraft(),
        )


def test_missing_weight_limits_incomplete():
    result = validate_from_revision(
        revision(include_limits=False),
        (),
        aircraft(),
    )

    assert result.validation.status == WBValidationStatus.INCOMPLETE
    assert not result.passed


def test_missing_envelope_incomplete():
    result = validate_from_revision(
        revision(include_envelope=False),
        (),
        aircraft(),
    )

    assert result.validation.status == WBValidationStatus.INCOMPLETE
    assert not result.passed


def test_wrong_aircraft_rejected():
    wrong_aircraft = aircraft()
    wrong_aircraft.id = "aircraft-999"

    with pytest.raises(ConfigurationAdapterError):
        validate_from_revision(
            revision(),
            (),
            wrong_aircraft,
        )


def test_registration_mismatch_rejected():
    wrong_aircraft = aircraft()
    wrong_aircraft.registration = "5H-WRONG"

    with pytest.raises(ConfigurationAdapterError):
        validate_from_revision(
            revision(),
            (),
            wrong_aircraft,
        )


def test_revision_identity_preserved():
    result = validate_from_revision(
        revision(),
        (),
        aircraft(),
    )

    assert result.calculation.configuration_revision_id == "revision-003"
    assert result.validation.configuration_revision_id == "revision-003"
    assert result.validation.configuration_revision_number == 3


def test_limit_change_is_revision_specific():
    original = revision()
    modified = deepcopy(original)

    modified.id = "revision-004"
    modified.revision_number = 4

    modified.snapshot["weight_balance"]["weight_limits"][
        "maximum_takeoff_weight_kg"
    ] = 850
    modified.snapshot["weight_balance"]["weight_limits"][
        "maximum_landing_weight_kg"
    ] = 850

    first = validate_from_revision(original, (), aircraft())
    second = validate_from_revision(modified, (), aircraft())

    assert first.validation.status == WBValidationStatus.PASS
    assert second.validation.status == WBValidationStatus.FAIL

    assert first.validation.configuration_revision_id == "revision-003"
    assert second.validation.configuration_revision_id == "revision-004"


def test_envelope_change_is_revision_specific():
    original = revision()
    modified = deepcopy(original)

    modified.id = "revision-004"
    modified.revision_number = 4

    modified.snapshot["weight_balance"]["longitudinal_cg_envelope"]["points"] = [
        {
            "weight_kg": 700,
            "forward_limit_mm": 2000,
            "aft_limit_mm": 2400,
        },
        {
            "weight_kg": 1100,
            "forward_limit_mm": 2100,
            "aft_limit_mm": 2450,
        },
    ]

    first = validate_from_revision(original, (), aircraft())
    second = validate_from_revision(modified, (), aircraft())

    assert first.validation.status == WBValidationStatus.PASS
    assert second.validation.status == WBValidationStatus.FAIL


def test_invalid_revision_number_rejected():
    with pytest.raises(ConfigurationAdapterError):
        validate_from_revision(
            revision(revision_number=0),
            (),
            aircraft(),
        )


def test_plot_service_preserves_revision_identity():
    plot = build_cg_plot_from_revision(
        revision(),
        (),
        aircraft(),
        label="Takeoff",
    )

    assert plot.aircraft_profile_id == "aircraft-001"
    assert plot.configuration_revision_id == "revision-003"
    assert plot.configuration_revision_number == 3
    assert plot.loading_points[0].label == "Takeoff"


def test_plot_service_uses_revision_envelope():
    original = revision()
    modified = deepcopy(original)

    modified.id = "revision-004"
    modified.revision_number = 4

    modified.snapshot["weight_balance"]["longitudinal_cg_envelope"]["points"][0][
        "forward_limit_mm"
    ] = 2250

    first = build_cg_plot_from_revision(original, (), aircraft())
    second = build_cg_plot_from_revision(modified, (), aircraft())

    assert first.envelope.forward_boundary[0].cg_mm == 2200
    assert second.envelope.forward_boundary[0].cg_mm == 2250


def test_plot_service_rejects_wrong_aircraft():
    wrong_aircraft = aircraft()
    wrong_aircraft.id = "aircraft-999"

    with pytest.raises(ConfigurationAdapterError):
        build_cg_plot_from_revision(
            revision(),
            (),
            wrong_aircraft,
        )
