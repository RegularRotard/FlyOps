"""Automatic per-leg fuel reconciliation.

Planned fuel consumption comes from the unified fuel planner.

Tank-specific consumption and refuelling must be provided explicitly.

This service does not assume tank feed order, validate physical tank
capacities, or establish operational fuel adequacy.
"""

from dataclasses import dataclass
from math import isfinite

from flightops.operations.services.unified_fuel_planning import (
    UnifiedFuelPlanningResult,
)

TOLERANCE_KG = 1e-6


@dataclass(frozen=True)
class TankQuantity:
    """Fuel quantity in one identified tank."""

    tank_id: str
    kilograms: float

    def __post_init__(self):
        if not self.tank_id.strip():
            raise ValueError("Tank ID cannot be empty.")

        if not isfinite(self.kilograms) or self.kilograms < 0:
            raise ValueError("Tank fuel must be finite and non-negative.")


@dataclass(frozen=True)
class LegTankAllocation:
    """Explicit tank consumption and pre-leg refuelling."""

    leg_id: str
    consumption: tuple[TankQuantity, ...]
    refuel_before_leg: tuple[TankQuantity, ...] = ()

    def __post_init__(self):
        if not self.leg_id.strip():
            raise ValueError("Leg ID cannot be empty.")


@dataclass(frozen=True)
class ReconciledLegFuel:
    """Calculated departure and arrival tank states."""

    leg_id: str

    departure_tanks: tuple[TankQuantity, ...]
    arrival_tanks: tuple[TankQuantity, ...]

    departure_fuel_kg: float
    consumed_fuel_kg: float
    arrival_fuel_kg: float

    refuel_before_leg_kg: float


@dataclass(frozen=True)
class FuelReconciliationResult:
    """Complete fuel reconciliation for an operation."""

    legs: tuple[ReconciledLegFuel, ...]

    initial_fuel_kg: float
    total_refuel_kg: float
    total_consumption_kg: float
    final_fuel_kg: float


def _quantity_map(
    quantities: tuple[TankQuantity, ...],
    *,
    permitted_tanks: set[str] | None = None,
) -> dict[str, float]:
    """Validate and convert tank quantities to an ID-based mapping."""

    result = {}

    for quantity in quantities:
        if quantity.tank_id in result:
            raise ValueError(f"Duplicate tank ID: {quantity.tank_id}")

        if permitted_tanks is not None and quantity.tank_id not in permitted_tanks:
            raise ValueError(f"Unknown tank ID: {quantity.tank_id}")

        result[quantity.tank_id] = quantity.kilograms

    return result


def _snapshot(
    tanks: dict[str, float],
) -> tuple[TankQuantity, ...]:
    """Create an immutable snapshot in stable tank order."""

    return tuple(
        TankQuantity(
            tank_id=tank_id,
            kilograms=kilograms,
        )
        for tank_id, kilograms in tanks.items()
    )


def calculate_fuel_reconciliation(
    fuel_plan: UnifiedFuelPlanningResult,
    initial_tanks: tuple[TankQuantity, ...],
    allocations: tuple[LegTankAllocation, ...],
) -> FuelReconciliationResult:
    """Reconcile explicit tank consumption with planned leg fuel.

    Refuelling is applied before the corresponding leg.

    Each leg's tank consumption must equal its planned consumption.
    """

    if not fuel_plan.legs:
        raise ValueError("Fuel plan must contain at least one leg.")

    if not initial_tanks:
        raise ValueError("At least one fuel tank is required.")

    tanks = _quantity_map(initial_tanks)
    permitted_tanks = set(tanks)

    planned_ids = tuple(leg.leg_id for leg in fuel_plan.legs)
    allocation_ids = tuple(item.leg_id for item in allocations)

    if allocation_ids != planned_ids:
        raise ValueError(
            "Tank allocations must match planned flight legs "
            "exactly and in the same order."
        )

    initial_fuel = sum(tanks.values())

    total_refuel = 0.0
    total_consumption = 0.0

    results = []

    for planned_leg, allocation in zip(
        fuel_plan.legs,
        allocations,
        strict=True,
    ):
        refuel = _quantity_map(
            allocation.refuel_before_leg,
            permitted_tanks=permitted_tanks,
        )

        consumption = _quantity_map(
            allocation.consumption,
            permitted_tanks=permitted_tanks,
        )

        refuel_total = sum(refuel.values())
        consumption_total = sum(consumption.values())

        if not isclose_fuel(
            consumption_total,
            planned_leg.planned_fuel_kg,
        ):
            raise ValueError(
                f"Tank consumption does not match planned "
                f"fuel for leg {planned_leg.leg_id}."
            )

        for tank_id, quantity in refuel.items():
            tanks[tank_id] += quantity

        departure = _snapshot(tanks)
        departure_total = sum(tanks.values())

        for tank_id, quantity in consumption.items():
            remaining = tanks[tank_id] - quantity

            if remaining < -TOLERANCE_KG:
                raise ValueError(
                    f"Insufficient fuel in tank {tank_id} for leg {planned_leg.leg_id}."
                )

            tanks[tank_id] = max(0.0, remaining)

        arrival = _snapshot(tanks)
        arrival_total = sum(tanks.values())

        if not isclose_fuel(
            departure_total - consumption_total,
            arrival_total,
        ):
            raise ValueError("Fuel mass balance failed.")

        results.append(
            ReconciledLegFuel(
                leg_id=planned_leg.leg_id,
                departure_tanks=departure,
                arrival_tanks=arrival,
                departure_fuel_kg=departure_total,
                consumed_fuel_kg=consumption_total,
                arrival_fuel_kg=arrival_total,
                refuel_before_leg_kg=refuel_total,
            )
        )

        total_refuel += refuel_total
        total_consumption += consumption_total

    final_fuel = sum(tanks.values())

    for name, value in (
        ("Initial fuel", initial_fuel),
        ("Total refuel", total_refuel),
        ("Total consumption", total_consumption),
        ("Final fuel", final_fuel),
    ):
        if not isfinite(value):
            raise ValueError(f"{name} must be finite.")

    if not isclose_fuel(
        initial_fuel + total_refuel - total_consumption,
        final_fuel,
    ):
        raise ValueError("Operation-wide fuel mass balance failed.")

    return FuelReconciliationResult(
        legs=tuple(results),
        initial_fuel_kg=initial_fuel,
        total_refuel_kg=total_refuel,
        total_consumption_kg=total_consumption,
        final_fuel_kg=final_fuel,
    )


def isclose_fuel(a: float, b: float) -> bool:
    """Compare fuel masses using a fixed absolute tolerance."""

    return isfinite(a) and isfinite(b) and abs(a - b) <= TOLERANCE_KG
