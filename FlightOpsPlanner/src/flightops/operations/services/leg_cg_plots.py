"""Revision-bound CG plotting data for individual flight legs.

Uses previously calculated W&B assessments. No new loading
or CG calculations are performed here.

These graphs are planning presentations, not flight approvals.
"""

from dataclasses import dataclass, replace

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import AircraftConfiguration
from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.operations.services.leg_weight_balance import (
    LegWeightBalanceResult,
    OperationWeightBalanceResult,
)
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
)
from flightops.weight_balance.plot_data import (
    CGPlotData,
    build_cg_plot_data,
    build_cg_plot_loading_point,
)


@dataclass(frozen=True)
class LegCGPlotResult:
    """Graph data associated with one flight leg."""

    leg_id: str
    sequence_number: int
    plot: CGPlotData

    departure_location_id: str | None = None
    destination_location_id: str | None = None


@dataclass(frozen=True)
class OperationCGPlotResult:
    """CG plotting data for every leg in an operation."""

    operation_id: str
    aircraft_profile_id: str
    configuration_revision_id: str
    legs: tuple[LegCGPlotResult, ...]


def _validate_assessment_identity(
    leg: LegWeightBalanceResult,
    operation: OperationWeightBalanceResult,
    revision: AircraftProfileRevision,
) -> None:
    """Ensure all loading conditions use the selected revision."""

    for assessment in (
        leg.zero_fuel,
        leg.departure,
        leg.arrival,
    ):
        validation = assessment.validation

        if validation.aircraft_profile_id != operation.aircraft_profile_id:
            raise ConfigurationAdapterError(
                "Leg assessment references a different aircraft."
            )

        if validation.configuration_revision_id != revision.id:
            raise ConfigurationAdapterError(
                "Leg assessment references a different configuration revision."
            )

        if validation.configuration_revision_number != revision.revision_number:
            raise ConfigurationAdapterError(
                "Leg assessment revision number does not match."
            )


def build_operation_cg_plots(
    operation: OperationWeightBalanceResult,
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
) -> OperationCGPlotResult:
    """Build separate CG graph data for every flight leg."""

    if operation.aircraft_profile_id != aircraft.id:
        raise ConfigurationAdapterError("Operation references a different aircraft.")

    if operation.configuration_revision_id != revision.id:
        raise ConfigurationAdapterError(
            "Operation references a different configuration revision."
        )

    if revision.profile_id != aircraft.id:
        raise ConfigurationAdapterError(
            "Configuration revision belongs to a different aircraft."
        )

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    if (
        configuration.registration != aircraft.registration
        or configuration.serial_number != aircraft.serial_number
        or configuration.variant_id != aircraft.variant_id
    ):
        raise ConfigurationAdapterError(
            "Configuration identity does not match the aircraft."
        )

    wb = configuration.weight_balance

    if wb is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    envelope = wb.longitudinal_cg_envelope

    plots = []

    for leg in operation.legs:
        _validate_assessment_identity(
            leg,
            operation,
            revision,
        )

        # Existing plotting function creates the departure point.
        departure_plot = build_cg_plot_data(
            leg.departure,
            envelope,
            label="Departure",
        )

        # Each loading condition retains its own validation result.
        zero_fuel = build_cg_plot_loading_point(
            leg.zero_fuel,
            label="Zero-Fuel Weight",
        )

        arrival = build_cg_plot_loading_point(
            leg.arrival,
            label="Arrival Weight",
        )

        plot = replace(
            departure_plot,
            zero_fuel_point=zero_fuel.point,
            zero_fuel_assessment=zero_fuel,
            arrival_assessment=arrival,
        )

        plots.append(
            LegCGPlotResult(
                leg_id=leg.leg_id,
                sequence_number=leg.sequence_number,
                plot=plot,
                departure_location_id=leg.departure_location_id,
                destination_location_id=leg.destination_location_id,
            )
        )

    return OperationCGPlotResult(
        operation_id=operation.operation_id,
        aircraft_profile_id=operation.aircraft_profile_id,
        configuration_revision_id=revision.id,
        legs=tuple(plots),
    )
