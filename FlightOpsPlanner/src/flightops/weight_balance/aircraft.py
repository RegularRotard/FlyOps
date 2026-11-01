"""Aircraft-specific weight and balance loading definitions."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from flightops.weight_balance.models import LoadItem
from flightops.weight_balance.units import (
    LengthUnit,
    MassUnit,
    convert_length,
    convert_mass,
)


class StationType(StrEnum):
    CREW = "crew"
    PASSENGER = "passenger"
    BAGGAGE = "baggage"
    EQUIPMENT = "equipment"
    FUEL = "fuel"
    OTHER = "other"


@dataclass(frozen=True)
class LoadingStation:
    """An aircraft loading station referenced to a specified datum."""

    station_id: str
    name: str
    station_type: StationType
    arm: float
    arm_unit: LengthUnit

    def __post_init__(self):
        if not self.station_id.strip():
            raise ValueError("Station ID cannot be empty.")

        if not self.name.strip():
            raise ValueError("Station name cannot be empty.")

        if not isfinite(self.arm):
            raise ValueError("Station arm must be finite.")

    @property
    def arm_mm(self) -> float:
        return convert_length(
            self.arm,
            self.arm_unit,
            LengthUnit.MM,
        )


@dataclass(frozen=True)
class AircraftWBSpecification:
    """Aircraft-specific loading stations and reference datum."""

    aircraft_id: str
    datum_description: str
    stations: tuple[LoadingStation, ...]

    def __post_init__(self):
        if not self.aircraft_id.strip():
            raise ValueError("Aircraft ID cannot be empty.")

        if not self.datum_description.strip():
            raise ValueError("Reference datum description is required.")

        station_ids = [station.station_id for station in self.stations]

        if len(station_ids) != len(set(station_ids)):
            raise ValueError("Loading station IDs must be unique.")

    def get_station(self, station_id: str) -> LoadingStation:
        for station in self.stations:
            if station.station_id == station_id:
                return station

        raise ValueError(f"Unknown loading station: {station_id}")


@dataclass(frozen=True)
class LoadAssignment:
    """A load assigned to an aircraft loading station."""

    station_id: str
    name: str
    weight: float
    weight_unit: MassUnit

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Load name cannot be empty.")

        if not isfinite(self.weight) or self.weight < 0:
            raise ValueError("Load weight must be non-negative and finite.")


def resolve_loads(
    specification: AircraftWBSpecification,
    assignments: tuple[LoadAssignment, ...],
) -> tuple[LoadItem, ...]:
    """Convert station assignments into normalized calculation loads."""

    resolved = []

    for assignment in assignments:
        station = specification.get_station(assignment.station_id)

        resolved.append(
            LoadItem(
                name=assignment.name,
                weight_kg=convert_mass(
                    assignment.weight,
                    assignment.weight_unit,
                    MassUnit.KG,
                ),
                arm_mm=station.arm_mm,
            )
        )

    return tuple(resolved)
