"""Revision-bound CG plotting service.

Application-facing entry point for producing CG plotting data.
The loading assessment and plotted envelope originate from the
same aircraft configuration revision.
"""

from dataclasses import replace

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import AircraftConfiguration
from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
)
from flightops.weight_balance.plot_data import (
    CGPlotData,
    CGPlotPoint,
    build_cg_plot_data,
    build_cg_plot_loading_point,
)
from flightops.weight_balance.revision_validation import validate_from_revision
from flightops.weight_balance.validation import WBWeightCheck
from flightops.weight_balance.zero_fuel import calculate_zero_fuel_from_revision


def build_cg_plot_from_revision(
    revision: AircraftProfileRevision,
    assignments: tuple[WBLoadAssignment, ...],
    aircraft: AircraftProfile,
    *,
    weight_check: WBWeightCheck = WBWeightCheck.TAKEOFF,
    label: str = "Loading condition",
) -> CGPlotData:
    """Build CG plotting data using one validated aircraft revision."""

    assessment = validate_from_revision(
        revision,
        assignments,
        aircraft,
        weight_check=weight_check,
    )

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    if configuration.weight_balance is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    envelope = configuration.weight_balance.longitudinal_cg_envelope

    return build_cg_plot_data(
        assessment,
        envelope,
        label=label,
    )


def build_fuel_loading_plot_from_revision(
    revision: AircraftProfileRevision,
    assignments: tuple[WBLoadAssignment, ...],
    aircraft: AircraftProfile,
) -> CGPlotData:
    """Build a CG graph containing takeoff and zero-fuel conditions."""

    assessment = calculate_zero_fuel_from_revision(
        revision,
        assignments,
        aircraft,
    )

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    wb = configuration.weight_balance

    if wb is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    zero_fuel = assessment.zero_fuel.validation

    plot = build_cg_plot_data(
        assessment.takeoff,
        wb.longitudinal_cg_envelope,
        label="Takeoff",
        zero_fuel_point=CGPlotPoint(
            cg_mm=zero_fuel.cg_mm,
            weight_kg=zero_fuel.total_weight_kg,
        ),
    )

    zfw_loading_point = build_cg_plot_loading_point(
        assessment.zero_fuel,
        label="Zero-Fuel Weight",
    )

    return replace(
        plot,
        zero_fuel_assessment=zfw_loading_point,
    )
