"""End-to-end flight planning integration.

Connects flight-day fuel planning, tank reconciliation, fuel timing,
operational fuel continuity and revision-bound weight and balance.

All tank allocations must be explicitly supplied.

This service does not establish operational fuel adequacy or
constitute flight-release approval.
"""

from dataclasses import dataclass
from math import isclose, isfinite

from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.fuel.configuration import FuelPhase, FuelPlanningConfiguration
from flightops.operations.schemas.flight import FlightOperation
from flightops.operations.schemas.flight_planning import FlightPlanningLeg
from flightops.operations.services.automatic_fuel_reconciliation import (
    FuelReconciliationResult,
    LegTankAllocation,
    TankQuantity,
    calculate_fuel_reconciliation,
)
from flightops.operations.services.flight_day_fuel import EngineCycleAllowance
from flightops.operations.services.fuel_timing import (
    TankFuelTiming,
    TimedLegFuel,
    calculate_timed_leg_fuel,
)
from flightops.operations.services.reconciled_operation import (
    ReconciledOperationResult,
    build_reconciled_operation,
)
from flightops.operations.services.timed_weight_balance import (
    TimedOperationWBResult,
    calculate_timed_operation_weight_balance,
)
from flightops.operations.services.unified_fuel_planning import (
    UnifiedFuelPlanningResult,
    calculate_unified_fuel_plan,
)

FUEL_TOLERANCE_KG = 1e-6


@dataclass(frozen=True)
class LegFuelTimingAllocation:
    """Tank-specific consumption before, during and after flight."""

    leg_id: str
    tanks: tuple[TankFuelTiming, ...]


@dataclass(frozen=True)
class IntegratedFlightPlanningResult:
    """Results from the complete planning calculation chain."""

    operation: FlightOperation
    fuel_plan: UnifiedFuelPlanningResult
    reconciliation: FuelReconciliationResult
    reconciled_operation: ReconciledOperationResult
    timed_fuel: tuple[TimedLegFuel, ...]
    weight_balance: TimedOperationWBResult


def _same_mass(first: float, second: float) -> bool:
    """Compare finite fuel masses with the accounting tolerance."""

    return (
        isfinite(first)
        and isfinite(second)
        and isclose(
            first,
            second,
            rel_tol=0,
            abs_tol=FUEL_TOLERANCE_KG,
        )
    )


def calculate_integrated_flight_plan(
    operation: FlightOperation,
    planning_legs: tuple[FlightPlanningLeg, ...],
    fuel_configuration: FuelPlanningConfiguration,
    initial_tanks: tuple[TankQuantity, ...],
    tank_allocations: tuple[LegTankAllocation, ...],
    timing_allocations: tuple[LegFuelTimingAllocation, ...],
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
    *,
    allowance: EngineCycleAllowance | None = None,
    engine_running_at_start: bool = False,
) -> IntegratedFlightPlanningResult:
    """Calculate and validate an integrated multi-leg flight plan."""

    operation_ids = tuple(leg.leg_id for leg in operation.legs)
    planning_ids = tuple(leg.leg_id for leg in planning_legs)
    allocation_ids = tuple(item.leg_id for item in tank_allocations)
    timing_ids = tuple(item.leg_id for item in timing_allocations)

    if not (operation_ids == planning_ids == allocation_ids == timing_ids):
        raise ValueError(
            "Operation, planning, tank allocation and timing "
            "leg IDs must match exactly and in order."
        )

    if operation.aircraft_profile_id != aircraft.id:
        raise ValueError("Operation references a different aircraft.")

    if operation.configuration_revision_id != revision.id:
        raise ValueError("Operation references a different aircraft revision.")

    # Additional idle time is not yet divided into
    # pre-takeoff and post-landing periods.
    for leg in planning_legs:
        if leg.additional_idle_minutes != 0:
            raise ValueError(
                "Additional idle time must be assigned to "
                "pre-takeoff or post-landing before integrated "
                "W&B calculations are available."
            )

    fuel_plan = calculate_unified_fuel_plan(
        operation_ids,
        planning_legs,
        fuel_configuration,
        allowance=allowance,
        engine_running_at_start=engine_running_at_start,
    )

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan,
        initial_tanks,
        tank_allocations,
    )

    reconciled_operation = build_reconciled_operation(
        operation,
        reconciliation,
        tank_allocations,
    )

    flight_rate = fuel_configuration.rate_for_phase(
        FuelPhase.FLIGHT
    ).consumption_kg_per_hour

    idle_rate = fuel_configuration.rate_for_phase(
        FuelPhase.IDLE
    ).consumption_kg_per_hour

    timed_results = []

    for planned, reconciled, allocation in zip(
        fuel_plan.legs,
        reconciliation.legs,
        timing_allocations,
        strict=True,
    ):
        before_takeoff_kg = planned.startup_minutes * idle_rate / 60.0

        airborne_kg = planned.planned_flight_minutes * flight_rate / 60.0

        after_landing_kg = planned.shutdown_minutes * idle_rate / 60.0

        expected_total = before_takeoff_kg + airborne_kg + after_landing_kg

        if not _same_mass(
            expected_total,
            planned.planned_fuel_kg,
        ):
            raise ValueError(
                f"Fuel phase totals do not match the plan for leg {planned.leg_id}."
            )

        timed = calculate_timed_leg_fuel(
            reconciled,
            allocation.tanks,
            expected_before_takeoff_kg=before_takeoff_kg,
            expected_airborne_kg=airborne_kg,
            expected_after_landing_kg=after_landing_kg,
        )

        timed_results.append(timed)

    timed_fuel = tuple(timed_results)

    wb = calculate_timed_operation_weight_balance(
        reconciled_operation.operation,
        timed_fuel,
        revision,
        aircraft,
    )

    return IntegratedFlightPlanningResult(
        operation=reconciled_operation.operation,
        fuel_plan=fuel_plan,
        reconciliation=reconciliation,
        reconciled_operation=reconciled_operation,
        timed_fuel=timed_fuel,
        weight_balance=wb,
    )
