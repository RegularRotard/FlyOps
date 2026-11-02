"""Presentation data for longitudinal weight-and-balance CG graphs.

This module prepares already validated loading results for plotting.

It does not calculate aircraft loading or independently determine
whether loading is within aircraft limitations.

All graph data is for assessment and must not be interpreted as
flight-release authorisation.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from flightops.aircraft.schemas.configuration import LongitudinalCGEnvelope
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    WBVerificationLevel,
)
from flightops.weight_balance.validation import WBValidationStatus


class WBPlotStatus(StrEnum):
    WITHIN_LIMITS = "within_limits"
    OUTSIDE_LIMITS = "outside_limits"
    INCOMPLETE = "incomplete"
    DEVELOPMENT = "development"


@dataclass(frozen=True)
class CGPlotPoint:
    """One point on a longitudinal CG graph."""

    cg_mm: float
    weight_kg: float


@dataclass(frozen=True)
class CGPlotEnvelope:
    """Ordered CG envelope boundaries suitable for plotting."""

    forward_boundary: tuple[CGPlotPoint, ...]
    aft_boundary: tuple[CGPlotPoint, ...]
    polygon: tuple[CGPlotPoint, ...]


@dataclass(frozen=True)
class CGPlotLoadingPoint:
    """A calculated aircraft loading condition."""

    label: str
    point: CGPlotPoint
    status: WBPlotStatus
    weight_margin_kg: float | None
    forward_margin_mm: float | None
    aft_margin_mm: float | None
    findings: tuple[str, ...]


@dataclass(frozen=True)
class CGPlotData:
    """Complete presentation data for a longitudinal CG graph."""

    aircraft_profile_id: str
    configuration_revision_id: str
    configuration_revision_number: int
    verification_level: WBVerificationLevel

    envelope: CGPlotEnvelope | None
    loading_points: tuple[CGPlotLoadingPoint, ...]

    zero_fuel_point: CGPlotPoint | None = None
    zero_fuel_assessment: CGPlotLoadingPoint | None = None
    arrival_assessment: CGPlotLoadingPoint | None = None


def build_cg_plot_envelope(
    envelope: LongitudinalCGEnvelope | None,
) -> CGPlotEnvelope | None:
    """Convert configured CG limits into ordered plotting coordinates."""

    if envelope is None:
        return None

    forward = tuple(
        CGPlotPoint(
            cg_mm=point.forward_limit_mm,
            weight_kg=point.weight_kg,
        )
        for point in envelope.points
    )

    aft = tuple(
        CGPlotPoint(
            cg_mm=point.aft_limit_mm,
            weight_kg=point.weight_kg,
        )
        for point in envelope.points
    )

    polygon = forward + tuple(reversed(aft))

    return CGPlotEnvelope(
        forward_boundary=forward,
        aft_boundary=aft,
        polygon=polygon,
    )


def _plot_status(result: RevisionBoundWBResult) -> WBPlotStatus:
    """Translate existing validation results into display status."""

    validation_status = result.validation.status

    if validation_status == WBValidationStatus.FAIL:
        return WBPlotStatus.OUTSIDE_LIMITS

    if validation_status == WBValidationStatus.INCOMPLETE:
        return WBPlotStatus.INCOMPLETE

    if result.verification_level != WBVerificationLevel.VERIFIED:
        return WBPlotStatus.DEVELOPMENT

    return WBPlotStatus.WITHIN_LIMITS


def build_cg_plot_loading_point(
    result: RevisionBoundWBResult,
    *,
    label: str = "Loading condition",
) -> CGPlotLoadingPoint:
    """Prepare a previously validated loading result for display."""

    validation = result.validation
    cg_evaluation = validation.cg_evaluation

    weight = validation.total_weight_kg
    cg = validation.cg_mm

    if not isfinite(weight) or not isfinite(cg):
        raise ValueError("Cannot plot a loading point with non-finite coordinates.")

    return CGPlotLoadingPoint(
        label=label,
        point=CGPlotPoint(
            cg_mm=cg,
            weight_kg=weight,
        ),
        status=_plot_status(result),
        weight_margin_kg=validation.weight_margin_kg,
        forward_margin_mm=cg_evaluation.forward_margin_mm,
        aft_margin_mm=cg_evaluation.aft_margin_mm,
        findings=validation.findings,
    )


def build_cg_plot_data(
    result: RevisionBoundWBResult,
    envelope: LongitudinalCGEnvelope | None,
    *,
    label: str = "Loading condition",
    zero_fuel_point: CGPlotPoint | None = None,
) -> CGPlotData:
    """Build complete CG graph data for one validated loading condition."""

    loading_point = build_cg_plot_loading_point(
        result,
        label=label,
    )

    return CGPlotData(
        aircraft_profile_id=result.validation.aircraft_profile_id,
        configuration_revision_id=result.validation.configuration_revision_id,
        configuration_revision_number=(result.validation.configuration_revision_number),
        verification_level=result.verification_level,
        envelope=build_cg_plot_envelope(envelope),
        loading_points=(loading_point,),
        zero_fuel_point=zero_fuel_point,
    )
