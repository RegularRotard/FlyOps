"""Revision-bound zero-fuel weight and balance calculations.

Zero-fuel loading excludes assignments at stations explicitly
classified as usable fuel.

Results are mathematical assessments, not flight-release approval.
"""

from dataclasses import dataclass
from math import isclose, isfinite

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    LoadingStationCategory,
)
from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    validate_from_revision,
)
from flightops.weight_balance.validation import WBWeightCheck


@dataclass(frozen=True)
class ZeroFuelWBResult:
    """Takeoff and zero-fuel assessments from one aircraft revision."""

    takeoff: RevisionBoundWBResult
    zero_fuel: RevisionBoundWBResult
    usable_fuel_weight_kg: float

    @property
    def aircraft_profile_id(self) -> str:
        return self.takeoff.validation.aircraft_profile_id

    @property
    def configuration_revision_id(self) -> str:
        return self.takeoff.validation.configuration_revision_id


def calculate_zero_fuel_from_revision(
    revision: AircraftProfileRevision,
    assignments: tuple[WBLoadAssignment, ...],
    aircraft: AircraftProfile,
) -> ZeroFuelWBResult:
    """Calculate takeoff and zero-fuel conditions from one revision."""

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

    if not wb.usable_fuel_classification_reviewed:
        raise ConfigurationAdapterError(
            "Usable-fuel station classifications have not "
            "been reviewed for this aircraft configuration."
        )

    fuel_stations = [
        station
        for station in wb.loading_stations
        if station.category == LoadingStationCategory.USABLE_FUEL
    ]

    if not fuel_stations:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no explicitly classified usable-fuel stations."
        )

    station_lookup = {station.station_id: station for station in wb.loading_stations}

    usable_fuel_assignments = []
    zero_fuel_assignments = []

    for assignment in assignments:
        station = station_lookup.get(assignment.station_id)

        if station is None:
            raise ConfigurationAdapterError(
                f"Unknown aircraft loading station: {assignment.station_id}"
            )

        if station.category == LoadingStationCategory.USABLE_FUEL:
            usable_fuel_assignments.append(assignment)
        else:
            zero_fuel_assignments.append(assignment)

    takeoff = validate_from_revision(
        revision,
        assignments,
        aircraft,
        weight_check=WBWeightCheck.TAKEOFF,
    )

    zero_fuel = validate_from_revision(
        revision,
        tuple(zero_fuel_assignments),
        aircraft,
        weight_check=WBWeightCheck.TAKEOFF,
    )

    takeoff_weight = takeoff.validation.total_weight_kg
    zero_fuel_weight = zero_fuel.validation.total_weight_kg

    fuel_weight = takeoff_weight - zero_fuel_weight

    if not isfinite(fuel_weight) or fuel_weight < 0:
        raise ConfigurationAdapterError("Calculated usable fuel weight is invalid.")

    if not isclose(
        zero_fuel_weight + fuel_weight,
        takeoff_weight,
        rel_tol=1e-9,
        abs_tol=1e-6,
    ):
        raise ConfigurationAdapterError(
            "Zero-fuel and takeoff weights are inconsistent."
        )

    return ZeroFuelWBResult(
        takeoff=takeoff,
        zero_fuel=zero_fuel,
        usable_fuel_weight_kg=fuel_weight,
    )
