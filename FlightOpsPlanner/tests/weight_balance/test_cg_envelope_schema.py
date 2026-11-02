"""Tests for aircraft weight limits and longitudinal CG envelope schemas."""

import pytest
from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftWeightLimits,
    CGEnvelopePoint,
    LongitudinalCGEnvelope,
)


def test_valid_weight_limits():
    limits = AircraftWeightLimits(
        maximum_takeoff_weight_kg=1100,
        maximum_landing_weight_kg=1050,
    )

    assert limits.maximum_takeoff_weight_kg == 1100
    assert limits.maximum_landing_weight_kg == 1050


def test_landing_weight_above_takeoff_rejected():
    with pytest.raises(ValidationError):
        AircraftWeightLimits(
            maximum_takeoff_weight_kg=1100,
            maximum_landing_weight_kg=1200,
        )


def test_minimum_weight_above_takeoff_rejected():
    with pytest.raises(ValidationError):
        AircraftWeightLimits(
            maximum_takeoff_weight_kg=1100,
            minimum_operating_weight_kg=1200,
        )


def test_valid_cg_envelope():
    envelope = LongitudinalCGEnvelope(
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

    assert len(envelope.points) == 2


def test_reversed_cg_limits_rejected():
    with pytest.raises(ValidationError):
        CGEnvelopePoint(
            weight_kg=700,
            forward_limit_mm=2700,
            aft_limit_mm=2200,
        )


def test_duplicate_envelope_weights_rejected():
    with pytest.raises(ValidationError):
        LongitudinalCGEnvelope(
            points=[
                CGEnvelopePoint(
                    weight_kg=700,
                    forward_limit_mm=2200,
                    aft_limit_mm=2700,
                ),
                CGEnvelopePoint(
                    weight_kg=700,
                    forward_limit_mm=2300,
                    aft_limit_mm=2600,
                ),
            ]
        )


def test_unordered_envelope_weights_rejected():
    with pytest.raises(ValidationError):
        LongitudinalCGEnvelope(
            points=[
                CGEnvelopePoint(
                    weight_kg=1100,
                    forward_limit_mm=2300,
                    aft_limit_mm=2600,
                ),
                CGEnvelopePoint(
                    weight_kg=700,
                    forward_limit_mm=2200,
                    aft_limit_mm=2700,
                ),
            ]
        )
