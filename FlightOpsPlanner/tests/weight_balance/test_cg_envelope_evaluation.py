"""Tests for longitudinal CG envelope evaluation."""

import pytest

from flightops.aircraft.schemas.configuration import (
    CGEnvelopePoint,
    LongitudinalCGEnvelope,
)
from flightops.weight_balance.envelope import (
    CGEvaluationStatus,
    evaluate_longitudinal_cg,
)


@pytest.fixture
def envelope():
    """Fictional envelope for software testing only."""

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


def test_within_limits(envelope):
    result = evaluate_longitudinal_cg(900, 2500, envelope)

    assert result.within_limits
    assert result.status == CGEvaluationStatus.WITHIN_LIMITS


def test_forward_limit_exceeded(envelope):
    result = evaluate_longitudinal_cg(900, 2200, envelope)

    assert result.status == CGEvaluationStatus.FORWARD_LIMIT_EXCEEDED


def test_aft_limit_exceeded(envelope):
    result = evaluate_longitudinal_cg(900, 2700, envelope)

    assert result.status == CGEvaluationStatus.AFT_LIMIT_EXCEEDED


def test_linear_interpolation(envelope):
    result = evaluate_longitudinal_cg(900, 2500, envelope)

    assert result.forward_limit_mm == pytest.approx(2250)
    assert result.aft_limit_mm == pytest.approx(2650)


def test_forward_boundary_accepted(envelope):
    result = evaluate_longitudinal_cg(900, 2250, envelope)

    assert result.within_limits


def test_aft_boundary_accepted(envelope):
    result = evaluate_longitudinal_cg(900, 2650, envelope)

    assert result.within_limits


def test_below_envelope_weight(envelope):
    result = evaluate_longitudinal_cg(600, 2500, envelope)

    assert result.status == CGEvaluationStatus.WEIGHT_OUTSIDE_ENVELOPE


def test_above_envelope_weight(envelope):
    result = evaluate_longitudinal_cg(1200, 2500, envelope)

    assert result.status == CGEvaluationStatus.WEIGHT_OUTSIDE_ENVELOPE


def test_missing_configuration():
    result = evaluate_longitudinal_cg(900, 2500, None)

    assert result.status == CGEvaluationStatus.CONFIGURATION_MISSING
    assert not result.within_limits


@pytest.mark.parametrize(
    ("weight", "cg"),
    [
        (float("nan"), 2500),
        (float("inf"), 2500),
        (900, float("nan")),
        (900, float("inf")),
        (-100, 2500),
        (0, 2500),
    ],
)
def test_invalid_inputs(envelope, weight, cg):
    result = evaluate_longitudinal_cg(weight, cg, envelope)

    assert result.status == CGEvaluationStatus.INVALID_INPUT
    assert not result.within_limits


def test_forward_margin(envelope):
    result = evaluate_longitudinal_cg(900, 2500, envelope)

    assert result.forward_margin_mm == pytest.approx(250)


def test_aft_margin(envelope):
    result = evaluate_longitudinal_cg(900, 2500, envelope)

    assert result.aft_margin_mm == pytest.approx(150)
