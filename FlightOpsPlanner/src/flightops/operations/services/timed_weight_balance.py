"""Revision-bound W&B using takeoff and landing fuel snapshots.

Operational fuel continuity uses before-start and after-shutdown fuel.
Weight and balance uses takeoff and landing fuel.

This module does not modify the original operation or fuel records.
Results are planning assessments, not operational flight approval.
"""

from dataclasses import dataclass
from math import isclose, isfinite

from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
)
from flightops.operations.services.fuel_timing import TimedLegFuel
from flightops.operations.services.leg_weight_balance import (
    LegWeightBalanceResult,
    calculate_leg_weight_balance,
)

TOLERANCE_KG = 1e-6


@dataclass(frozen=True)
class TimedOperationWBResult:
    """W&B assessments using flight-phase fuel quantities."""

    operation_id: str
    aircraft_profile_id: str
    configuration_revision_id: str
    legs: tuple[LegWeightBalanceResult, ...]


def _same_mass(first: float, second: float) -> bool:
    """Compare finite fuel masses within the accounting tolerance."""

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


def build_timed_wb_leg(
    leg: FlightLeg,
    timing: TimedLegFuel,
) -> FlightLeg:
    """Build a validated W&B leg from takeoff and landing fuel states.

    The original operational fuel state remains unchanged.
    """

    if leg.leg_id != timing.leg_id:
        raise ValueError("Fuel timing references a different flight leg.")

    original = {tank.station_id: tank for tank in leg.fuel.tanks}

    before_start = {tank.tank_id: tank.kilograms for tank in timing.before_start_tanks}

    takeoff = {tank.tank_id: tank.kilograms for tank in timing.takeoff_tanks}

    landing = {tank.tank_id: tank.kilograms for tank in timing.landing_tanks}

    after_shutdown = {
        tank.tank_id: tank.kilograms for tank in timing.after_shutdown_tanks
    }

    station_ids = set(original)

    if not station_ids or any(
        set(state) != station_ids
        for state in (
            before_start,
            takeoff,
            landing,
            after_shutdown,
        )
    ):
        raise ValueError(f"Fuel station mismatch for leg {leg.leg_id}.")

    for name, state, expected_total in (
        ("Before-start", before_start, timing.before_start_fuel_kg),
        ("Takeoff", takeoff, timing.takeoff_fuel_kg),
        ("Landing", landing, timing.landing_fuel_kg),
        ("After-shutdown", after_shutdown, timing.after_shutdown_fuel_kg),
    ):
        if not _same_mass(sum(state.values()), expected_total):
            raise ValueError(f"{name} fuel total mismatch for leg {leg.leg_id}.")

    wb_tanks = []

    for station_id, original_tank in original.items():
        initial_kg = original_tank.departure_fuel_kg
        final_kg = original_tank.arrival_fuel_kg

        if not _same_mass(initial_kg, before_start[station_id]):
            raise ValueError(f"Before-start fuel mismatch at {station_id}.")

        if not _same_mass(final_kg, after_shutdown[station_id]):
            raise ValueError(f"After-shutdown fuel mismatch at {station_id}.")

        departure_kg = takeoff[station_id]
        arrival_kg = landing[station_id]

        if (
            not isfinite(departure_kg)
            or not isfinite(arrival_kg)
            or departure_kg < 0
            or arrival_kg < 0
        ):
            raise ValueError(f"Invalid W&B fuel quantity at {station_id}.")

        if departure_kg + TOLERANCE_KG < arrival_kg:
            raise ValueError(f"Landing fuel exceeds takeoff fuel at {station_id}.")

        if (
            departure_kg > initial_kg + TOLERANCE_KG
            or arrival_kg < final_kg - TOLERANCE_KG
        ):
            raise ValueError(f"Fuel timing sequence is inconsistent at {station_id}.")

        airborne_burn_kg = max(
            0.0,
            departure_kg - arrival_kg,
        )

        wb_tanks.append(
            LegFuelTank(
                station_id=station_id,
                departure_fuel_kg=departure_kg,
                planned_burn_kg=airborne_burn_kg,
            )
        )

    # Construct and validate a new leg.
    # Do not overwrite the original operational fuel state.
    return FlightLeg.model_validate(
        {
            **leg.model_dump(),
            "fuel": LegFuelState(tanks=wb_tanks).model_dump(),
        }
    )


def calculate_timed_operation_weight_balance(
    operation: FlightOperation,
    timings: tuple[TimedLegFuel, ...],
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
) -> TimedOperationWBResult:
    """Calculate revision-bound W&B for every timed flight leg."""

    if operation.aircraft_profile_id != aircraft.id:
        raise ValueError("Flight operation references a different aircraft.")

    if operation.configuration_revision_id != revision.id:
        raise ValueError(
            "Flight operation references a different configuration revision."
        )

    operation_ids = tuple(leg.leg_id for leg in operation.legs)

    timing_ids = tuple(timing.leg_id for timing in timings)

    if operation_ids != timing_ids:
        raise ValueError(
            "Fuel timing must match operation flight legs exactly and in order."
        )

    results = []

    for leg, timing in zip(
        operation.legs,
        timings,
        strict=True,
    ):
        wb_leg = build_timed_wb_leg(
            leg,
            timing,
        )

        results.append(
            calculate_leg_weight_balance(
                wb_leg,
                revision,
                aircraft,
            )
        )

    return TimedOperationWBResult(
        operation_id=operation.operation_id,
        aircraft_profile_id=aircraft.id,
        configuration_revision_id=revision.id,
        legs=tuple(results),
    )
