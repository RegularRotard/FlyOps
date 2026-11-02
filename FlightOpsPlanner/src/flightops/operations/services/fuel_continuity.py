"""Fuel continuity validation between consecutive flight legs.

Fuel is tracked by configured station ID.

An increase in fuel must be explained by a recorded refuelling
quantity. Unmodelled defuelling, tank transfers, and ground
consumption are not supported.

Results are planning checks, not operational fuel approvals.
"""

from dataclasses import dataclass
from math import isclose

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flightops.operations.schemas.flight import FlightOperation

FUEL_TOLERANCE_KG = 1e-6


class RefuelQuantity(BaseModel):
    """Fuel added to one tank between flight legs."""

    model_config = ConfigDict(extra="forbid")

    station_id: str = Field(min_length=1)

    quantity_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )


class RefuelEvent(BaseModel):
    """Refuelling recorded between two consecutive flight legs."""

    model_config = ConfigDict(extra="forbid")

    after_leg_id: str = Field(min_length=1)
    before_leg_id: str = Field(min_length=1)

    quantities: list[RefuelQuantity] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_event(self):
        if self.after_leg_id == self.before_leg_id:
            raise ValueError("Refuelling must occur between different flight legs.")

        station_ids = [quantity.station_id for quantity in self.quantities]

        if len(station_ids) != len(set(station_ids)):
            raise ValueError("Refuelling station identifiers must be unique.")

        return self


@dataclass(frozen=True)
class TankContinuityResult:
    """Expected and planned fuel for one tank at a leg transition."""

    station_id: str
    previous_arrival_kg: float
    refuelled_kg: float
    expected_departure_kg: float
    planned_departure_kg: float


@dataclass(frozen=True)
class FuelTransitionResult:
    """Fuel reconciliation between consecutive legs."""

    after_leg_id: str
    before_leg_id: str
    tanks: tuple[TankContinuityResult, ...]


@dataclass(frozen=True)
class FuelContinuityResult:
    """Fuel reconciliation for a complete operation."""

    operation_id: str
    transitions: tuple[FuelTransitionResult, ...]


class FuelContinuityError(ValueError):
    """Raised when planned fuel quantities cannot be reconciled."""


def validate_fuel_continuity(
    operation: FlightOperation,
    refuel_events: tuple[RefuelEvent, ...] = (),
) -> FuelContinuityResult:
    """Reconcile fuel quantities across all consecutive flight legs."""

    valid_transitions = {
        (previous.leg_id, current.leg_id)
        for previous, current in zip(
            operation.legs,
            operation.legs[1:],
        )
    }

    events_by_transition = {}

    for event in refuel_events:
        key = (event.after_leg_id, event.before_leg_id)

        if key not in valid_transitions:
            raise FuelContinuityError(
                "Refuelling event does not reference consecutive flight legs."
            )

        if key in events_by_transition:
            raise FuelContinuityError(
                "Duplicate refuelling event for a flight-leg transition."
            )

        events_by_transition[key] = event

    transitions = []

    for previous, current in zip(
        operation.legs,
        operation.legs[1:],
    ):
        key = (previous.leg_id, current.leg_id)
        event = events_by_transition.get(key)

        previous_tanks = {tank.station_id: tank for tank in previous.fuel.tanks}

        current_tanks = {tank.station_id: tank for tank in current.fuel.tanks}

        if previous_tanks.keys() != current_tanks.keys():
            raise FuelContinuityError(
                "Consecutive legs must use the same fuel tank stations."
            )

        refuelled = (
            {quantity.station_id: quantity.quantity_kg for quantity in event.quantities}
            if event is not None
            else {}
        )

        unknown_tanks = refuelled.keys() - previous_tanks.keys()

        if unknown_tanks:
            raise FuelContinuityError(
                "Refuelling references an unknown fuel tank station."
            )

        tank_results = []

        for station_id, previous_tank in previous_tanks.items():
            current_tank = current_tanks[station_id]

            previous_arrival = previous_tank.arrival_fuel_kg
            added = refuelled.get(station_id, 0.0)

            expected_departure = previous_arrival + added
            planned_departure = current_tank.departure_fuel_kg

            if not isclose(
                expected_departure,
                planned_departure,
                rel_tol=0,
                abs_tol=FUEL_TOLERANCE_KG,
            ):
                raise FuelContinuityError(
                    "Fuel continuity mismatch at station "
                    f"'{station_id}' between legs "
                    f"'{previous.leg_id}' and '{current.leg_id}': "
                    f"expected {expected_departure:.3f} kg, "
                    f"planned {planned_departure:.3f} kg."
                )

            tank_results.append(
                TankContinuityResult(
                    station_id=station_id,
                    previous_arrival_kg=previous_arrival,
                    refuelled_kg=added,
                    expected_departure_kg=expected_departure,
                    planned_departure_kg=planned_departure,
                )
            )

        transitions.append(
            FuelTransitionResult(
                after_leg_id=previous.leg_id,
                before_leg_id=current.leg_id,
                tanks=tuple(tank_results),
            )
        )

    return FuelContinuityResult(
        operation_id=operation.operation_id,
        transitions=tuple(transitions),
    )
