"""Convert per-leg passenger manifests to aircraft loading assignments.

This module does not define aircraft station arms or limitations.
Those must come from the selected aircraft configuration revision.
"""

from dataclasses import dataclass

from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)
from flightops.weight_balance.configuration_adapter import (
    WBLoadAssignment,
)
from flightops.weight_balance.units import MassUnit


class ManifestLoadingError(ValueError):
    """Raised when a manifest cannot be converted into aircraft loads."""


@dataclass(frozen=True)
class LegStationAssignments:
    """Loading station selections for one flight leg."""

    leg_uid: str

    # Record ID -> configured aircraft station ID
    passenger_stations: dict[str, str]
    baggage_stations: dict[str, str]


@dataclass(frozen=True)
class ManifestLoadingResult:
    """Calculated loading inputs for one flight leg."""

    leg_uid: str
    assignments: tuple[WBLoadAssignment, ...]
    passenger_weight_kg: float
    baggage_weight_kg: float

    @property
    def total_payload_kg(self) -> float:
        return self.passenger_weight_kg + self.baggage_weight_kg


def build_manifest_loading(
    manifest: LegManifest,
    station_assignments: LegStationAssignments,
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
    *,
    configured_station_ids: set[str],
) -> ManifestLoadingResult:
    """Build W&B loading inputs from one complete leg manifest.

    Reject missing weights, missing stations and unknown records.
    Station IDs must exist in the selected aircraft configuration.

    The returned assignments do not include aircraft empty weight,
    crew, fuel or other installed equipment.
    """

    if manifest.leg_uid != station_assignments.leg_uid:
        raise ManifestLoadingError(
            "Manifest and station assignments belong to different legs."
        )

    if not configured_station_ids:
        raise ManifestLoadingError(
            "Aircraft loading stations have not been configured."
        )

    result = []
    passenger_total = 0.0
    baggage_total = 0.0

    used_passenger_stations = set()

    for passenger_id in sorted(manifest.passenger_ids):
        passenger = passengers.get(passenger_id)

        if passenger is None:
            raise ManifestLoadingError(f"Unknown passenger: {passenger_id}")

        weight = passenger.effective_weight_kg

        if weight is None:
            raise ManifestLoadingError(
                f"Missing weight for passenger: {passenger.name}"
            )

        station_id = station_assignments.passenger_stations.get(passenger_id)

        if not station_id:
            raise ManifestLoadingError(
                f"No loading station selected for: {passenger.name}"
            )

        if station_id not in configured_station_ids:
            raise ManifestLoadingError(
                f"Unknown aircraft loading station: {station_id}"
            )

        if station_id in used_passenger_stations:
            raise ManifestLoadingError(
                f"Multiple passengers assigned to station: {station_id}"
            )

        used_passenger_stations.add(station_id)

        result.append(
            WBLoadAssignment(
                station_id=station_id,
                name=passenger.name,
                weight=weight,
                weight_unit=MassUnit.KG,
            )
        )

        passenger_total += weight

    for baggage_id in sorted(manifest.baggage_ids):
        item = baggage.get(baggage_id)

        if item is None:
            raise ManifestLoadingError(f"Unknown baggage item: {baggage_id}")

        weight = item.effective_weight_kg

        if weight is None:
            raise ManifestLoadingError(
                f"Missing weight for baggage: {item.description}"
            )

        station_id = station_assignments.baggage_stations.get(baggage_id)

        if not station_id:
            raise ManifestLoadingError(
                f"No loading station selected for baggage: {item.description}"
            )

        if station_id not in configured_station_ids:
            raise ManifestLoadingError(
                f"Unknown aircraft loading station: {station_id}"
            )

        result.append(
            WBLoadAssignment(
                station_id=station_id,
                name=item.description,
                weight=weight,
                weight_unit=MassUnit.KG,
            )
        )

        baggage_total += weight

    return ManifestLoadingResult(
        leg_uid=manifest.leg_uid,
        assignments=tuple(result),
        passenger_weight_kg=passenger_total,
        baggage_weight_kg=baggage_total,
    )
