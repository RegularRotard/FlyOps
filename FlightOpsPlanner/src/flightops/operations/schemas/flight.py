"""Validated models for multi-leg flight operations.

These models describe planned operations and do not constitute
operational flight approval.

All fuel quantities are expressed as mass in kilograms.
All loading assignments are tied to configured aircraft stations.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flightops.operations.schemas.flight_planning import FlightType


class LegLoadCategory(StrEnum):
    """Types of non-fuel loads carried on a flight leg."""

    CREW = "crew"
    PASSENGER = "passenger"
    BAGGAGE = "baggage"
    CARGO = "cargo"
    OTHER = "other"


class FlightLocation(BaseModel):
    """A departure or destination location."""

    model_config = ConfigDict(extra="forbid")

    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class LegLoadAssignment(BaseModel):
    """One non-fuel loading assignment on a specific flight leg."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: str = Field(min_length=1)

    station_id: str = Field(min_length=1)

    name: str = Field(min_length=1)

    category: LegLoadCategory

    weight_kg: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    person_id: str | None = None

    @model_validator(mode="after")
    def validate_person_assignment(self):
        """Require a person ID for crew and passenger assignments."""

        requires_person_id = self.category in (
            LegLoadCategory.CREW,
            LegLoadCategory.PASSENGER,
        )

        if requires_person_id and not self.person_id:
            raise ValueError("Crew and passenger assignments require a person ID.")

        return self


class LegFuelTank(BaseModel):
    """Fuel mass assigned to one aircraft fuel station."""

    model_config = ConfigDict(extra="forbid")

    station_id: str = Field(min_length=1)

    departure_fuel_kg: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    planned_burn_kg: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_burn(self):
        if self.planned_burn_kg > self.departure_fuel_kg:
            raise ValueError("Planned fuel burn exceeds departure fuel.")

        return self

    @property
    def arrival_fuel_kg(self) -> float:
        """Planned fuel remaining at arrival."""
        return self.departure_fuel_kg - self.planned_burn_kg


class LegFuelState(BaseModel):
    """Fuel distribution across the aircraft's usable-fuel stations."""

    model_config = ConfigDict(extra="forbid")

    tanks: list[LegFuelTank] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_tanks(self):
        station_ids = [tank.station_id for tank in self.tanks]

        if len(station_ids) != len(set(station_ids)):
            raise ValueError("Fuel tank station identifiers must be unique.")

        return self

    @property
    def departure_fuel_kg(self) -> float:
        return sum(tank.departure_fuel_kg for tank in self.tanks)

    @property
    def planned_burn_kg(self) -> float:
        return sum(tank.planned_burn_kg for tank in self.tanks)

    @property
    def arrival_fuel_kg(self) -> float:
        return sum(tank.arrival_fuel_kg for tank in self.tanks)


class FlightLeg(BaseModel):
    """One independently planned leg of a flight operation."""

    model_config = ConfigDict(extra="forbid")
    leg_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=1)
    flight_type: FlightType | None = None
    departure: FlightLocation
    destination: FlightLocation
    loads: list[LegLoadAssignment] = Field(default_factory=list)
    fuel: LegFuelState

    @model_validator(mode="after")
    def validate_leg(self):
        if (
            self.departure.location_id == self.destination.location_id
            and self.flight_type != FlightType.SCENIC
        ):
            raise ValueError(
                "Departure and destination must be different except for Scenic flights."
            )
        assignment_ids = [assignment.assignment_id for assignment in self.loads]

        if len(assignment_ids) != len(set(assignment_ids)):
            raise ValueError("Load assignment IDs must be unique within a leg.")

        person_ids = [
            assignment.person_id
            for assignment in self.loads
            if assignment.person_id is not None
        ]

        if len(person_ids) != len(set(person_ids)):
            raise ValueError("A person cannot be assigned twice to the same leg.")

        return self


class FlightOperation(BaseModel):
    """A complete operation consisting of one or more flight legs."""

    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)

    aircraft_profile_id: str = Field(min_length=1)

    configuration_revision_id: str = Field(min_length=1)

    legs: list[FlightLeg] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operation(self):
        leg_ids = [leg.leg_id for leg in self.legs]

        if len(leg_ids) != len(set(leg_ids)):
            raise ValueError("Flight leg IDs must be unique.")

        sequences = [leg.sequence_number for leg in self.legs]

        expected = list(range(1, len(self.legs) + 1))

        if sequences != expected:
            raise ValueError("Flight legs must be ordered sequentially starting at 1.")

        for previous, current in zip(self.legs, self.legs[1:]):
            if previous.destination.location_id != current.departure.location_id:
                raise ValueError(
                    "Consecutive flight legs must have "
                    "matching arrival and departure locations."
                )

        return self
