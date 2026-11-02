"""Connect existing flight-leg identities to fuel-planning calculations.

The existing flight-operation model remains authoritative.

This service validates that fuel-planning records correspond to
the same flight legs, in the same order.

It does not modify weight-and-balance or fuel-continuity states.
"""

from dataclasses import dataclass
from math import isfinite

from flightops.fuel.configuration import FuelPlanningConfiguration
from flightops.operations.schemas.flight_planning import (
    FlightPlanningLeg,
    FlightType,
)
from flightops.operations.services.flight_day_fuel import (
    EngineCycleAllowance,
    FlightDayFuelResult,
    calculate_flight_day_fuel,
)


@dataclass(frozen=True)
class UnifiedLegFuel:
    """Fuel-planning result associated with an existing flight leg."""

    leg_id: str
    flight_type: FlightType
    planned_flight_minutes: float
    startup_minutes: float
    shutdown_minutes: float
    additional_idle_minutes: float
    planned_fuel_kg: float


@dataclass(frozen=True)
class UnifiedFuelPlanningResult:
    """Operation-wide fuel-planning summary."""

    legs: tuple[UnifiedLegFuel, ...]
    total_flight_minutes: float
    total_idle_minutes: float
    total_planned_fuel_kg: float
    final_engine_running: bool


def calculate_unified_fuel_plan(
    operation_leg_ids: tuple[str, ...],
    planning_legs: tuple[FlightPlanningLeg, ...],
    configuration: FuelPlanningConfiguration,
    *,
    allowance: EngineCycleAllowance | None = None,
    engine_running_at_start: bool = False,
) -> UnifiedFuelPlanningResult:
    """Calculate fuel for a validated sequence of existing flight legs."""

    if not operation_leg_ids:
        raise ValueError("Operation requires at least one flight leg.")

    if any(
        not isinstance(leg_id, str) or not leg_id.strip()
        for leg_id in operation_leg_ids
    ):
        raise ValueError("Operation leg IDs must be non-empty strings.")

    if len(set(operation_leg_ids)) != len(operation_leg_ids):
        raise ValueError("Operation leg IDs must be unique.")

    planning_ids = tuple(leg.leg_id for leg in planning_legs)

    if planning_ids != operation_leg_ids:
        raise ValueError(
            "Fuel-planning legs must match operation legs "
            "exactly, including their order."
        )

    calculated: FlightDayFuelResult = calculate_flight_day_fuel(
        planning_legs,
        configuration,
        allowance=allowance,
        engine_running_at_start=engine_running_at_start,
    )

    results = []

    for planning_leg, calculated_leg in zip(
        planning_legs,
        calculated.legs,
        strict=True,
    ):
        results.append(
            UnifiedLegFuel(
                leg_id=planning_leg.leg_id,
                flight_type=planning_leg.flight_type,
                planned_flight_minutes=planning_leg.planned_flight_minutes,
                startup_minutes=calculated_leg.startup_minutes,
                shutdown_minutes=calculated_leg.shutdown_minutes,
                additional_idle_minutes=(calculated_leg.additional_idle_minutes),
                planned_fuel_kg=calculated_leg.fuel.total_fuel.kilograms,
            )
        )

    if not isfinite(calculated.total_fuel_kg):
        raise ValueError("Total planned fuel must be finite.")

    return UnifiedFuelPlanningResult(
        legs=tuple(results),
        total_flight_minutes=calculated.total_flight_minutes,
        total_idle_minutes=calculated.total_idle_minutes,
        total_planned_fuel_kg=calculated.total_fuel_kg,
        final_engine_running=not planning_legs[-1].shutdown_after_leg,
    )
