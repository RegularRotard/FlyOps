"""Connect versioned aircraft configurations to the W&B calculator.

Calculations are mathematical development outputs, not operational
approval or confirmation that an aircraft is within its limitations.
"""

from dataclasses import dataclass
from math import isfinite

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    ConfigurationStatus,
)
from flightops.database.models import AircraftProfileRevision
from flightops.weight_balance.calculator import calculate_weight_balance
from flightops.weight_balance.models import LoadItem, WeightBalanceResult
from flightops.weight_balance.units import (
    LengthUnit,
    MassUnit,
    convert_length,
    convert_mass,
)


class ConfigurationAdapterError(ValueError):
    """Raised when a configuration cannot support a W&B calculation."""


@dataclass(frozen=True)
class WBLoadAssignment:
    """A load assigned to a configured aircraft station."""

    station_id: str
    name: str
    weight: float
    weight_unit: MassUnit

    def __post_init__(self):
        if not self.station_id.strip():
            raise ConfigurationAdapterError(
                "Loading station ID cannot be empty."
            )

        if not self.name.strip():
            raise ConfigurationAdapterError(
                "Load name cannot be empty."
            )

        if not isfinite(self.weight):
            raise ConfigurationAdapterError(
                "Load weight must be finite."
            )

        if self.weight < 0:
            raise ConfigurationAdapterError(
                "Load weight cannot be negative."
            )

        if not isinstance(self.weight_unit, MassUnit):
            raise ConfigurationAdapterError(
                "Load weight unit is invalid."
            )


@dataclass(frozen=True)
class VersionedWBResult:
    """A W&B calculation tied to an immutable configuration revision."""

    aircraft_profile_id: str
    configuration_revision_id: str
    configuration_revision_number: int
    calculation: WeightBalanceResult


def _normalized_mass(source, legacy_kg: float) -> float:
    if source is None:
        return legacy_kg

    return convert_mass(
        source.value,
        source.unit,
        MassUnit.KG,
    )


def _normalized_arm(source, legacy_mm: float) -> float:
    if source is None:
        return legacy_mm

    return convert_length(
        source.value,
        source.unit,
        LengthUnit.MM,
    )


def calculate_from_revision(
    revision: AircraftProfileRevision,
    assignments: tuple[WBLoadAssignment, ...],
) -> VersionedWBResult:
    """Calculate W&B using a specific aircraft configuration revision."""

    if revision.id is None or revision.profile_id is None:
        raise ConfigurationAdapterError(
            "A persisted aircraft configuration revision is required."
        )

    try:
        configuration = AircraftConfiguration.model_validate(
            revision.snapshot
        )
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    if configuration.status == ConfigurationStatus.DRAFT:
        raise ConfigurationAdapterError(
            "Draft aircraft configurations cannot be used for W&B calculations."
        )

    wb = configuration.weight_balance

    if wb is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    station_lookup = {
        station.station_id: station
        for station in wb.loading_stations
    }

    empty_weight = _normalized_mass(
        wb.basic_empty_weight,
        wb.basic_empty_weight_kg,
    )

    empty_arm = _normalized_arm(
        wb.basic_empty_weight_longitudinal_arm,
        wb.basic_empty_weight_longitudinal_arm_mm,
    )

    loads = [
        LoadItem(
            name="Basic empty aircraft",
            weight_kg=empty_weight,
            arm_mm=empty_arm,
        )
    ]
    station_totals: dict[str, float] = {}
    for assignment in assignments:
        station = station_lookup.get(assignment.station_id)

        if station is None:
            raise ConfigurationAdapterError(
                f"Unknown aircraft loading station: {assignment.station_id}"
            )

        weight_kg = convert_mass(
            assignment.weight,
            assignment.weight_unit,
            MassUnit.KG,
        )

        arm_mm = _normalized_arm(
            station.longitudinal_arm,
            station.longitudinal_arm_mm,
        )

        maximum_load_kg = (
            _normalized_mass(
                station.maximum_load,
                station.maximum_load_kg,
            )
            if station.maximum_load is not None
            or station.maximum_load_kg is not None
            else None
        )

        station_totals[assignment.station_id] = (
            station_totals.get(assignment.station_id, 0.0)
            + weight_kg
        )

        if (
            maximum_load_kg is not None
            and station_totals[assignment.station_id] > maximum_load_kg
        ):
            raise ConfigurationAdapterError(
                f"Combined load at station '{station.station_id}' "
                "exceeds its configured maximum."
            )

        loads.append(
            LoadItem(
                name=assignment.name,
                weight_kg=weight_kg,
                arm_mm=arm_mm,
            )
        )

    result = calculate_weight_balance(loads)

    return VersionedWBResult(
        aircraft_profile_id=revision.profile_id,
        configuration_revision_id=revision.id,
        configuration_revision_number=revision.revision_number,
        calculation=result,
    )
