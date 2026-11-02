"""Tests for integrated weight and longitudinal CG validation."""

from types import SimpleNamespace

import pytest

from flightops.aircraft.schemas.configuration import (
    AircraftWeightLimits,
    CGEnvelopePoint,
    LongitudinalCGEnvelope,
)
from flightops.weight_balance.configuration_adapter import (
    VersionedWBResult,
)
from flightops.weight_balance.validation import (
    WBValidationStatus,
    WBWeightCheck,
    validate_weight_balance,
)


@pytest.fixture
def limits():
    return AircraftWeightLimits(
        maximum_takeoff_weight_kg=1100,
        maximum_landing_weight_kg=1050,
        minimum_operating_weight_kg=700,
    )


@pytest.fixture
def envelope():
    """Fictional envelope; not approved aircraft limitations."""

    return LongitudinalCGEnvelope(
        points=[
            CGEnvelopePoint(
                weight_kg=700,
                forward_limit_mm=2200,
                aft_limit_mm=2700,
            ),
            CGEnvelopePoint(
                weight_kg=1100,
                forward_limit_mm=2300,
                aft_limit_mm=2600,
            ),
        ]
    )


def calculation(weight=900, cg=2500):
    """Build a versioned result to isolate validation logic."""

    return VersionedWBResult(
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        configuration_revision_number=3,
        calculation=SimpleNamespace(
            total_weight_kg=weight,
            cg_mm=cg,
        ),
    )


def test_valid_takeoff_passes(limits, envelope):
    result = validate_weight_balance(
        calculation(),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.PASS
    assert result.passed
    assert result.weight_margin_kg == pytest.approx(200)


def test_revision_identity_preserved(limits, envelope):
    result = validate_weight_balance(
        calculation(),
        limits,
        envelope,
    )

    assert result.aircraft_profile_id == "aircraft-001"
    assert result.configuration_revision_id == "revision-003"
    assert result.configuration_revision_number == 3


def test_takeoff_weight_exceeded(limits, envelope):
    result = validate_weight_balance(
        calculation(weight=1150),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.FAIL
    assert result.weight_margin_kg == pytest.approx(-50)


def test_landing_weight_exceeded(limits, envelope):
    result = validate_weight_balance(
        calculation(weight=1075),
        limits,
        envelope,
        weight_check=WBWeightCheck.LANDING,
    )

    assert result.status == WBValidationStatus.FAIL
    assert result.weight_margin_kg == pytest.approx(-25)


def test_minimum_weight_violation(limits, envelope):
    result = validate_weight_balance(
        calculation(weight=650),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.FAIL
    assert any("Minimum" in finding for finding in result.findings)


def test_forward_cg_exceeded(limits, envelope):
    result = validate_weight_balance(
        calculation(cg=2100),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.FAIL


def test_aft_cg_exceeded(limits, envelope):
    result = validate_weight_balance(
        calculation(cg=2800),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.FAIL


def test_missing_weight_limits_is_incomplete(envelope):
    result = validate_weight_balance(
        calculation(),
        None,
        envelope,
    )

    assert result.status == WBValidationStatus.INCOMPLETE
    assert not result.passed


def test_missing_envelope_is_incomplete(limits):
    result = validate_weight_balance(
        calculation(),
        limits,
        None,
    )

    assert result.status == WBValidationStatus.INCOMPLETE


def test_known_failure_takes_priority_over_missing_envelope(limits):
    result = validate_weight_balance(
        calculation(weight=1200),
        limits,
        None,
    )

    assert result.status == WBValidationStatus.FAIL
    assert len(result.findings) >= 2


def test_missing_landing_limit_is_incomplete(envelope):
    limits = AircraftWeightLimits(
        maximum_takeoff_weight_kg=1100,
    )

    result = validate_weight_balance(
        calculation(),
        limits,
        envelope,
        weight_check=WBWeightCheck.LANDING,
    )

    assert result.status == WBValidationStatus.INCOMPLETE


def test_invalid_weight_check_rejected(limits, envelope):
    with pytest.raises(TypeError, match="Invalid weight check"):
        validate_weight_balance(
            calculation(),
            limits,
            envelope,
            weight_check="departure",
        )


def test_exact_takeoff_weight_limit_accepted(limits, envelope):
    result = validate_weight_balance(
        calculation(weight=1100),
        limits,
        envelope,
    )

    assert result.status == WBValidationStatus.PASS
    assert result.weight_margin_kg == pytest.approx(0)


def test_exact_landing_weight_limit_accepted(limits, envelope):
    result = validate_weight_balance(
        calculation(weight=1050),
        limits,
        envelope,
        weight_check=WBWeightCheck.LANDING,
    )

    assert result.status == WBValidationStatus.PASS
    assert result.weight_margin_kg == pytest.approx(0)
