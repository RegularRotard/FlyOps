"""Connect passenger manifests to revision-bound aircraft W&B.

The result is a partial loading assessment until all required
crew, fuel, equipment and other aircraft loads are included.

This module does not authorize flight operations.
"""

from dataclasses import dataclass

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    ConfigurationStatus,
)
from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
)
from flightops.operations.loading.manifest_adapter import (
    LegStationAssignments,
    ManifestLoadingResult,
    build_manifest_loading,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)
from flightops.weight_balance.configuration_adapter import (
    VersionedWBResult,
    calculate_from_revision,
)


class LoadingIntegrationError(ValueError):
    """An aircraft revision cannot support this loading operation."""


@dataclass(frozen=True)
class StationOption:
    """A loading station defined by an aircraft configuration revision."""

    station_id: str
    name: str
    category: str


@dataclass(frozen=True)
class PartialLegWBResult:
    """Calculated aircraft condition with incomplete operational loads."""

    leg_uid: str
    aircraft_profile_id: str
    configuration_revision_id: str
    configuration_revision_number: int

    payload: ManifestLoadingResult
    calculation: VersionedWBResult

    @property
    def total_weight_kg(self) -> float:
        return self.calculation.calculation.total_weight_kg

    @property
    def cg_mm(self) -> float:
        return self.calculation.calculation.cg_mm

    @property
    def complete_for_dispatch(self) -> bool:
        """Partial manifest W&B cannot establish dispatch readiness."""
        return False


def get_revision_loading_stations(
    revision: AircraftProfileRevision,
) -> tuple[StationOption, ...]:
    """Extract station IDs from a specific aircraft configuration revision."""

    if revision.id is None or revision.profile_id is None:
        raise LoadingIntegrationError(
            "A persisted aircraft configuration revision is required."
        )

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise LoadingIntegrationError(
            "Aircraft configuration revision is invalid."
        ) from exc

    if configuration.status == ConfigurationStatus.DRAFT:
        raise LoadingIntegrationError(
            "Draft aircraft configurations cannot be used for loading."
        )

    wb = configuration.weight_balance

    if wb is None:
        raise LoadingIntegrationError(
            "Aircraft configuration has no weight-and-balance data."
        )

    return tuple(
        StationOption(
            station_id=station.station_id,
            name=station.description,
            category=str(station.category.value),
        )
        for station in wb.loading_stations
    )


def calculate_partial_leg_wb(
    *,
    manifest: LegManifest,
    station_assignments: LegStationAssignments,
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
) -> PartialLegWBResult:
    """Calculate a partial aircraft W&B from one manifest.

    The existing revision-bound engine supplies empty aircraft
    weight, station arms and configured station weight limits.

    Crew, fuel and other non-manifest loads are not added here.
    """

    if aircraft.id is None:
        raise LoadingIntegrationError("A persisted aircraft profile is required.")

    stations = get_revision_loading_stations(revision)

    station_ids = {station.station_id for station in stations}

    station_categories = {station.station_id: station.category for station in stations}

    for passenger_id, station_id in station_assignments.passenger_stations.items():
        if passenger_id not in manifest.passenger_ids:
            continue

        if (
            station_id in station_categories
            and station_categories[station_id] != "passenger"
        ):
            raise LoadingIntegrationError(
                f"Passenger {passenger_id} is assigned to "
                f"a non-passenger station: {station_id}"
            )

    for baggage_id, station_id in station_assignments.baggage_stations.items():
        if baggage_id not in manifest.baggage_ids:
            continue

        if station_id in station_categories and station_categories[station_id] not in (
            "baggage",
            "cargo",
        ):
            raise LoadingIntegrationError(
                f"Baggage {baggage_id} is assigned to "
                f"an unsuitable station: {station_id}"
            )

    payload = build_manifest_loading(
        manifest,
        station_assignments,
        passengers,
        baggage,
        configured_station_ids=station_ids,
    )

    result = calculate_from_revision(
        revision,
        payload.assignments,
        aircraft=aircraft,
    )

    return PartialLegWBResult(
        leg_uid=manifest.leg_uid,
        aircraft_profile_id=result.aircraft_profile_id,
        configuration_revision_id=result.configuration_revision_id,
        configuration_revision_number=(result.configuration_revision_number),
        payload=payload,
        calculation=result,
    )
