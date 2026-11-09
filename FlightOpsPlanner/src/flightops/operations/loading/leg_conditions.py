"""Additional aircraft loads for leg takeoff and landing W&B.

All weights use kilograms internally.

This module describes calculation inputs. It does not grant
operational approval or determine dispatch readiness.
"""

from dataclasses import dataclass
from math import isfinite


class LegConditionError(ValueError):
    """Invalid or incomplete leg loading condition."""


def _validate_weight(value: float, label: str) -> None:
    if not isfinite(value) or value < 0:
        raise LegConditionError(f"{label} must be finite and nonnegative.")


@dataclass(frozen=True)
class CrewLoad:
    """Crew member assigned to an aircraft loading station."""

    crew_id: str
    name: str
    station_id: str
    weight_kg: float

    def __post_init__(self):
        if not self.crew_id.strip():
            raise LegConditionError("Crew ID is required.")

        if not self.name.strip():
            raise LegConditionError("Crew name is required.")

        if not self.station_id.strip():
            raise LegConditionError("Crew station is required.")

        _validate_weight(self.weight_kg, "Crew weight")


@dataclass(frozen=True)
class FuelStationLoad:
    """Fuel quantity assigned to one aircraft fuel station."""

    station_id: str
    weight_kg: float

    def __post_init__(self):
        if not self.station_id.strip():
            raise LegConditionError("Fuel station is required.")

        _validate_weight(self.weight_kg, "Fuel weight")


@dataclass(frozen=True)
class OtherStationLoad:
    """Additional equipment or operational load."""

    name: str
    station_id: str
    weight_kg: float

    def __post_init__(self):
        if not self.name.strip():
            raise LegConditionError("Load name is required.")

        if not self.station_id.strip():
            raise LegConditionError("Load station is required.")

        _validate_weight(self.weight_kg, "Additional load weight")


@dataclass(frozen=True)
class LegLoadingConditions:
    """Inputs for one leg's takeoff and landing conditions.

    Fuel quantities represent actual total quantities at each
    respective condition, not merely fuel burned during the leg.
    """

    leg_uid: str

    crew: tuple[CrewLoad, ...]
    takeoff_fuel: tuple[FuelStationLoad, ...]
    landing_fuel: tuple[FuelStationLoad, ...]

    other_loads: tuple[OtherStationLoad, ...] = ()

    def __post_init__(self):
        if not self.leg_uid.strip():
            raise LegConditionError("Flight-leg UID is required.")

        crew_ids = [item.crew_id for item in self.crew]

        if len(crew_ids) != len(set(crew_ids)):
            raise LegConditionError("Duplicate crew IDs in one loading condition.")

        for label, fuel in (
            ("takeoff", self.takeoff_fuel),
            ("landing", self.landing_fuel),
        ):
            station_ids = [item.station_id for item in fuel]

            if len(station_ids) != len(set(station_ids)):
                raise LegConditionError(f"Duplicate {label} fuel station.")

        departure = {item.station_id: item.weight_kg for item in self.takeoff_fuel}

        arrival = {item.station_id: item.weight_kg for item in self.landing_fuel}

        if set(departure) != set(arrival):
            raise LegConditionError(
                "Takeoff and landing fuel must reference "
                "the same configured fuel stations."
            )

        for station_id, arrival_kg in arrival.items():
            if arrival_kg > departure[station_id]:
                raise LegConditionError(
                    "Landing fuel cannot exceed takeoff fuel "
                    f"at station {station_id} without an "
                    "explicit refuelling or transfer model."
                )

    @property
    def takeoff_fuel_kg(self) -> float:
        return sum(item.weight_kg for item in self.takeoff_fuel)

    @property
    def landing_fuel_kg(self) -> float:
        return sum(item.weight_kg for item in self.landing_fuel)

    @property
    def planned_fuel_consumption_kg(self) -> float:
        return self.takeoff_fuel_kg - self.landing_fuel_kg
