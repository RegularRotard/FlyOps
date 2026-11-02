"""Tests for longitudinal CG graph presentation data."""

from types import SimpleNamespace

import pytest

from flightops.aircraft.schemas.configuration import (
    CGEnvelopePoint,
    LongitudinalCGEnvelope,
)
from flightops.weight_balance.plot_data import (
    CGPlotPoint,
    WBPlotStatus,
    build_cg_plot_data,
    build_cg_plot_envelope,
    build_cg_plot_loading_point,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    WBVerificationLevel,
)
from flightops.weight_balance.validation import WBValidationStatus


def sample_envelope():
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


def sample_result(
    *,
    status=WBValidationStatus.PASS,
    verification=WBVerificationLevel.VERIFIED,
    weight=900.0,
    cg=2500.0,
):
    validation = SimpleNamespace(
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        configuration_revision_number=3,
        status=status,
        total_weight_kg=weight,
        cg_mm=cg,
        weight_margin_kg=200.0,
        cg_evaluation=SimpleNamespace(
            forward_margin_mm=250.0,
            aft_margin_mm=150.0,
        ),
        findings=(),
    )

    return RevisionBoundWBResult(
        calculation=SimpleNamespace(),
        validation=validation,
        verification_level=verification,
    )


def test_envelope_boundaries_preserve_coordinates():
    envelope = build_cg_plot_envelope(sample_envelope())

    assert envelope.forward_boundary == (
        CGPlotPoint(cg_mm=2200, weight_kg=700),
        CGPlotPoint(cg_mm=2300, weight_kg=1100),
    )

    assert envelope.aft_boundary == (
        CGPlotPoint(cg_mm=2700, weight_kg=700),
        CGPlotPoint(cg_mm=2600, weight_kg=1100),
    )


def test_polygon_follows_forward_then_reversed_aft():
    envelope = build_cg_plot_envelope(sample_envelope())

    assert envelope.polygon == (
        CGPlotPoint(2200, 700),
        CGPlotPoint(2300, 1100),
        CGPlotPoint(2600, 1100),
        CGPlotPoint(2700, 700),
    )


def test_missing_envelope_returns_none():
    assert build_cg_plot_envelope(None) is None


def test_verified_pass_is_within_limits():
    point = build_cg_plot_loading_point(sample_result())

    assert point.status == WBPlotStatus.WITHIN_LIMITS


def test_failed_validation_is_outside_limits():
    point = build_cg_plot_loading_point(sample_result(status=WBValidationStatus.FAIL))

    assert point.status == WBPlotStatus.OUTSIDE_LIMITS


def test_incomplete_validation_is_incomplete():
    point = build_cg_plot_loading_point(
        sample_result(status=WBValidationStatus.INCOMPLETE)
    )

    assert point.status == WBPlotStatus.INCOMPLETE


def test_development_configuration_not_shown_as_verified_pass():
    point = build_cg_plot_loading_point(
        sample_result(verification=WBVerificationLevel.DEVELOPMENT)
    )

    assert point.status == WBPlotStatus.DEVELOPMENT


def test_failure_takes_precedence_over_development_status():
    point = build_cg_plot_loading_point(
        sample_result(
            status=WBValidationStatus.FAIL,
            verification=WBVerificationLevel.DEVELOPMENT,
        )
    )

    assert point.status == WBPlotStatus.OUTSIDE_LIMITS


def test_loading_point_preserves_calculated_coordinates():
    point = build_cg_plot_loading_point(sample_result())

    assert point.point == CGPlotPoint(
        cg_mm=2500.0,
        weight_kg=900.0,
    )


def test_loading_point_preserves_margins():
    point = build_cg_plot_loading_point(sample_result())

    assert point.weight_margin_kg == 200.0
    assert point.forward_margin_mm == 250.0
    assert point.aft_margin_mm == 150.0


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_weight_rejected(invalid):
    with pytest.raises(ValueError):
        build_cg_plot_loading_point(sample_result(weight=invalid))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_cg_rejected(invalid):
    with pytest.raises(ValueError):
        build_cg_plot_loading_point(sample_result(cg=invalid))


def test_complete_plot_data_preserves_revision_identity():
    plot = build_cg_plot_data(
        sample_result(),
        sample_envelope(),
        label="Takeoff",
    )

    assert plot.aircraft_profile_id == "aircraft-001"
    assert plot.configuration_revision_id == "revision-003"
    assert plot.configuration_revision_number == 3
    assert plot.loading_points[0].label == "Takeoff"


def test_complete_plot_data_includes_envelope():
    plot = build_cg_plot_data(
        sample_result(),
        sample_envelope(),
    )

    assert plot.envelope is not None
    assert len(plot.envelope.polygon) == 4


def test_complete_plot_data_supports_missing_envelope():
    plot = build_cg_plot_data(
        sample_result(status=WBValidationStatus.INCOMPLETE),
        None,
    )

    assert plot.envelope is None
    assert plot.loading_points[0].status == WBPlotStatus.INCOMPLETE
