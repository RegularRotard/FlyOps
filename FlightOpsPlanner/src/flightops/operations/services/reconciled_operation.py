"""Connect reconciled fuel calculations to existing flight operations.

The adapter creates a new, validated FlightOperation containing
calculated fuel states. The original operation is not modified.

Tank IDs correspond to configured usable-fuel station IDs.

Results are planning data, not operational flight approval.
"""

from dataclasses import dataclass
from math import isclose, isfinite

from flightops.operations.schemas.flight import (
    FlightOperation,
    LegFuelState,
    LegFuelTank,
)
from flightops.operations.services.automatic_fuel_reconciliation import (
    FuelReconciliationResult,
    LegTankAllocation,
)
from flightops.operations.services.fuel_continuity import (
    FuelContinuityResult,
    RefuelEvent,
    RefuelQuantity,
    validate_fuel_continuity,
)

TOLERANCE_KG = 1e-6


@dataclass(frozen=True)
class ReconciledOperationResult:
    """Operation containing calculated, validated fuel quantities."""

    operation: FlightOperation

    refuel_events: tuple[RefuelEvent, ...]

    fuel_continuity: FuelContinuityResult

    reconciliation: FuelReconciliationResult


def _same_mass(first: float, second: float) -> bool:
    """Compare two finite fuel masses."""

    return (
        isfinite(first)
        and isfinite(second)
        and isclose(
            first,
            second,
            rel_tol=0,
            abs_tol=TOLERANCE_KG,
        )
    )


def build_reconciled_operation(
    operation: FlightOperation,
    reconciliation: FuelReconciliationResult,
    allocations: tuple[LegTankAllocation, ...],
) -> ReconciledOperationResult:
    """Populate operation fuel states from reconciled tank quantities.

    Existing route, passenger, baggage and cargo data are preserved.

    Refuelling is represented between consecutive flight legs.
    Refuelling before the first leg is not supported by this adapter.

    Reconciled tank IDs must match the operation's fuel station IDs.
    """

    operation_ids = tuple(leg.leg_id for leg in operation.legs)

    reconciliation_ids = tuple(leg.leg_id for leg in reconciliation.legs)

    allocation_ids = tuple(allocation.leg_id for allocation in allocations)

    if not (operation_ids == reconciliation_ids == allocation_ids):
        raise ValueError(
            "Operation, reconciliation and allocation legs "
            "must match exactly and in order."
        )

    if allocations[0].refuel_before_leg:
        raise ValueError(
            "Refuelling before the first leg must be included "
            "in the initial fuel quantities."
        )

    updated_legs = []
    refuel_events = []

    for index, (leg, reconciled, allocation) in enumerate(
        zip(
            operation.legs,
            reconciliation.legs,
            allocations,
            strict=True,
        )
    ):
        original_ids = {tank.station_id for tank in leg.fuel.tanks}

        departure = {
            tank.tank_id: tank.kilograms for tank in reconciled.departure_tanks
        }

        arrival = {tank.tank_id: tank.kilograms for tank in reconciled.arrival_tanks}

        consumed = {tank.tank_id: tank.kilograms for tank in allocation.consumption}

        if set(departure) != original_ids or set(arrival) != original_ids:
            raise ValueError(f"Fuel station mismatch on leg {leg.leg_id}.")

        expected_consumption = sum(consumed.values())

        if not _same_mass(
            expected_consumption,
            reconciled.consumed_fuel_kg,
        ):
            raise ValueError(f"Consumption mismatch on leg {leg.leg_id}.")

        if not _same_mass(
            sum(departure.values()),
            reconciled.departure_fuel_kg,
        ):
            raise ValueError(f"Departure total mismatch on leg {leg.leg_id}.")

        if not _same_mass(
            sum(arrival.values()),
            reconciled.arrival_fuel_kg,
        ):
            raise ValueError(f"Arrival total mismatch on leg {leg.leg_id}.")

        fuel_tanks = []

        for original_tank in leg.fuel.tanks:
            station_id = original_tank.station_id

            departure_kg = departure[station_id]
            arrival_kg = arrival[station_id]
            burn_kg = consumed.get(station_id, 0.0)

            if not _same_mass(
                departure_kg - burn_kg,
                arrival_kg,
            ):
                raise ValueError(f"Tank mass balance mismatch: {station_id}.")

            fuel_tanks.append(
                LegFuelTank(
                    station_id=station_id,
                    departure_fuel_kg=departure_kg,
                    planned_burn_kg=burn_kg,
                )
            )

        updated_leg = leg.model_copy(
            update={
                "fuel": LegFuelState(
                    tanks=fuel_tanks,
                ),
            },
            deep=True,
        )

        updated_legs.append(updated_leg)

        if index > 0 and allocation.refuel_before_leg:
            previous_leg = operation.legs[index - 1]

            refuel_events.append(
                RefuelEvent(
                    after_leg_id=previous_leg.leg_id,
                    before_leg_id=leg.leg_id,
                    quantities=[
                        RefuelQuantity(
                            station_id=quantity.tank_id,
                            quantity_kg=quantity.kilograms,
                        )
                        for quantity in allocation.refuel_before_leg
                        if quantity.kilograms > 0
                    ],
                )
            )

    # Revalidate the complete operation rather than relying
    # on Pydantic model_copy() to validate updated fields.
    updated_operation = FlightOperation.model_validate(
        {
            **operation.model_dump(),
            "legs": [leg.model_dump() for leg in updated_legs],
        }
    )

    continuity = validate_fuel_continuity(
        updated_operation,
        tuple(refuel_events),
    )

    return ReconciledOperationResult(
        operation=updated_operation,
        refuel_events=tuple(refuel_events),
        fuel_continuity=continuity,
        reconciliation=reconciliation,
    )
