"""Revision-bound takeoff and landing W&B for one flight leg.

Results are planning assessments, not flight-release authorisations.
"""

from dataclasses import dataclass

from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
)
from flightops.operations.loading.leg_conditions import (
    LegConditionError,
    LegLoadingConditions,
)
from flightops.operations.loading.manifest_adapter import (
    LegStationAssignments,
    build_manifest_loading,
)
from flightops.operations.loading.revision_bridge import (
    get_revision_loading_stations,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)
from flightops.weight_balance.configuration_adapter import (
    WBLoadAssignment,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    validate_from_revision,
)
from flightops.weight_balance.units import MassUnit
from flightops.weight_balance.validation import WBWeightCheck


@dataclass(frozen=True)
class LegWBConditionsResult:
    """Takeoff and landing assessments for one leg."""

    leg_uid: str
    takeoff: RevisionBoundWBResult
    landing: RevisionBoundWBResult

    crew_weight_kg: float
    payload_weight_kg: float

    takeoff_fuel_kg: float
    landing_fuel_kg: float

    @property
    def complete_for_dispatch(self) -> bool:
        """Planning calculations alone cannot authorize dispatch."""
        return False


def _require_station_category(
    station_lookup: dict[str, str],
    station_id: str,
    allowed: set[str],
    label: str,
) -> None:
    category = station_lookup.get(station_id)

    if category is None:
        raise LegConditionError(f"{label} uses unknown station: {station_id}")

    if category not in allowed:
        raise LegConditionError(
            f"{label} cannot use station {station_id} with category {category}."
        )


def calculate_leg_wb_conditions(
    *,
    manifest: LegManifest,
    station_assignments: LegStationAssignments,
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
    conditions: LegLoadingConditions,
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
) -> LegWBConditionsResult:
    """Calculate and validate takeoff and landing loading.

    The caller must supply operationally appropriate fuel,
    crew and other loads.

    The calculation does not certify that all required loads
    or aircraft-specific restrictions have been captured.
    """

    if conditions.leg_uid != manifest.leg_uid:
        raise LegConditionError("Loading conditions belong to another flight leg.")

    stations = get_revision_loading_stations(revision)

    station_lookup = {station.station_id: station.category for station in stations}

    configured_station_ids = set(station_lookup)

    payload = build_manifest_loading(
        manifest,
        station_assignments,
        passengers,
        baggage,
        configured_station_ids=configured_station_ids,
    )

    # Do not permit passenger or baggage loads at unrelated
    # aircraft stations, even if the station ID exists.
    for passenger_id in manifest.passenger_ids:
        station_id = station_assignments.passenger_stations.get(passenger_id)

        if station_id:
            _require_station_category(
                station_lookup,
                station_id,
                {"passenger"},
                "Passenger",
            )

    for baggage_id in manifest.baggage_ids:
        station_id = station_assignments.baggage_stations.get(baggage_id)

        if station_id:
            _require_station_category(
                station_lookup,
                station_id,
                {"baggage", "cargo"},
                "Baggage",
            )

    used_crew_stations = set()

    crew_assignments = []

    for crew in conditions.crew:
        _require_station_category(
            station_lookup,
            crew.station_id,
            {"crew"},
            "Crew",
        )

        if crew.station_id in used_crew_stations:
            raise LegConditionError(
                f"Multiple crew members assigned to one crew station: {crew.station_id}"
            )

        used_crew_stations.add(crew.station_id)

        crew_assignments.append(
            WBLoadAssignment(
                station_id=crew.station_id,
                name=crew.name,
                weight=crew.weight_kg,
                weight_unit=MassUnit.KG,
            )
        )

    other_assignments = []

    for load in conditions.other_loads:
        _require_station_category(
            station_lookup,
            load.station_id,
            {"cargo", "other"},
            "Additional load",
        )

        other_assignments.append(
            WBLoadAssignment(
                station_id=load.station_id,
                name=load.name,
                weight=load.weight_kg,
                weight_unit=MassUnit.KG,
            )
        )

    def fuel_assignments(fuel):
        result = []

        for item in fuel:
            _require_station_category(
                station_lookup,
                item.station_id,
                {"usable_fuel"},
                "Fuel",
            )

            result.append(
                WBLoadAssignment(
                    station_id=item.station_id,
                    name=f"Fuel — {item.station_id}",
                    weight=item.weight_kg,
                    weight_unit=MassUnit.KG,
                )
            )

        return tuple(result)

    common = (
        *payload.assignments,
        *crew_assignments,
        *other_assignments,
    )

    takeoff_assignments = (
        *common,
        *fuel_assignments(conditions.takeoff_fuel),
    )

    landing_assignments = (
        *common,
        *fuel_assignments(conditions.landing_fuel),
    )

    takeoff = validate_from_revision(
        revision,
        takeoff_assignments,
        aircraft,
        weight_check=WBWeightCheck.TAKEOFF,
    )

    landing = validate_from_revision(
        revision,
        landing_assignments,
        aircraft,
        weight_check=WBWeightCheck.LANDING,
    )

    return LegWBConditionsResult(
        leg_uid=manifest.leg_uid,
        takeoff=takeoff,
        landing=landing,
        crew_weight_kg=sum(crew.weight_kg for crew in conditions.crew),
        payload_weight_kg=payload.total_payload_kg,
        takeoff_fuel_kg=conditions.takeoff_fuel_kg,
        landing_fuel_kg=conditions.landing_fuel_kg,
    )
