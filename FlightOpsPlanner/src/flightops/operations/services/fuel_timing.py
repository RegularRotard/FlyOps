"""Fuel quantities at engine start, takeoff, landing and shutdown.

Fuel consumption must be explicitly allocated to configured tanks.

The service does not infer tank feed order or validate approved
fuel-system operating procedures.

Results are planning calculations, not operational approval.
"""

from dataclasses import dataclass
from math import isfinite

from flightops.operations.services.automatic_fuel_reconciliation import (
    ReconciledLegFuel,
    TankQuantity,
)

TOLERANCE_KG = 1e-6


@dataclass(frozen=True)
class TankFuelTiming:
    """Fuel consumed from one tank during three operating periods."""

    tank_id: str
    before_takeoff_kg: float
    airborne_kg: float
    after_landing_kg: float

    def __post_init__(self):
        if not self.tank_id.strip():
            raise ValueError("Tank ID cannot be empty.")

        for name, value in (
            ("Before-takeoff fuel", self.before_takeoff_kg),
            ("Airborne fuel", self.airborne_kg),
            ("After-landing fuel", self.after_landing_kg),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")


@dataclass(frozen=True)
class TimedLegFuel:
    """Fuel states at the relevant stages of one flight leg."""

    leg_id: str

    before_start_tanks: tuple[TankQuantity, ...]
    takeoff_tanks: tuple[TankQuantity, ...]
    landing_tanks: tuple[TankQuantity, ...]
    after_shutdown_tanks: tuple[TankQuantity, ...]

    before_start_fuel_kg: float
    takeoff_fuel_kg: float
    landing_fuel_kg: float
    after_shutdown_fuel_kg: float


def _same_mass(first: float, second: float) -> bool:
    return isfinite(first) and isfinite(second) and abs(first - second) <= TOLERANCE_KG


def calculate_timed_leg_fuel(
    reconciled: ReconciledLegFuel,
    allocations: tuple[TankFuelTiming, ...],
    *,
    expected_before_takeoff_kg: float,
    expected_airborne_kg: float,
    expected_after_landing_kg: float,
) -> TimedLegFuel:
    """Calculate takeoff and landing fuel from explicit allocations.

    The three expected phase totals must match the actual
    per-tank allocations.

    The final fuel state must agree with reconciliation.
    """

    if not allocations:
        raise ValueError("At least one tank timing allocation is required.")

    departure = {tank.tank_id: tank.kilograms for tank in reconciled.departure_tanks}

    arrival = {tank.tank_id: tank.kilograms for tank in reconciled.arrival_tanks}

    allocation_ids = [allocation.tank_id for allocation in allocations]

    if len(allocation_ids) != len(set(allocation_ids)):
        raise ValueError("Duplicate tank timing allocation.")

    if set(allocation_ids) != set(departure):
        raise ValueError("Timing allocations must match departure fuel tanks.")

    if set(arrival) != set(departure):
        raise ValueError("Departure and arrival tank identities do not match.")

    expected = (
        expected_before_takeoff_kg,
        expected_airborne_kg,
        expected_after_landing_kg,
    )

    if any(not isfinite(value) or value < 0 for value in expected):
        raise ValueError("Expected fuel consumption must be finite and non-negative.")

    before_total = sum(item.before_takeoff_kg for item in allocations)

    airborne_total = sum(item.airborne_kg for item in allocations)

    after_total = sum(item.after_landing_kg for item in allocations)

    for calculated, required in zip(
        (before_total, airborne_total, after_total),
        expected,
        strict=True,
    ):
        if not _same_mass(calculated, required):
            raise ValueError(
                "Fuel timing allocation does not match the expected phase consumption."
            )

    if not _same_mass(
        before_total + airborne_total + after_total,
        reconciled.consumed_fuel_kg,
    ):
        raise ValueError("Timed fuel consumption does not match reconciliation.")

    timing_by_tank = {item.tank_id: item for item in allocations}

    takeoff = {}
    landing = {}

    for tank_id, initial_kg in departure.items():
        timing = timing_by_tank[tank_id]

        takeoff_kg = initial_kg - timing.before_takeoff_kg

        landing_kg = takeoff_kg - timing.airborne_kg

        final_kg = landing_kg - timing.after_landing_kg

        if min(takeoff_kg, landing_kg, final_kg) < -TOLERANCE_KG:
            raise ValueError(f"Insufficient fuel in tank {tank_id}.")

        if not _same_mass(final_kg, arrival[tank_id]):
            raise ValueError(f"Final fuel mismatch in tank {tank_id}.")

        takeoff[tank_id] = max(0.0, takeoff_kg)
        landing[tank_id] = max(0.0, landing_kg)

    def snapshot(values):
        return tuple(
            TankQuantity(tank_id, quantity) for tank_id, quantity in values.items()
        )

    takeoff_total = sum(takeoff.values())
    landing_total = sum(landing.values())

    if not _same_mass(
        takeoff_total,
        reconciled.departure_fuel_kg - before_total,
    ):
        raise ValueError("Takeoff fuel mass balance failed.")

    if not _same_mass(
        landing_total,
        takeoff_total - airborne_total,
    ):
        raise ValueError("Landing fuel mass balance failed.")

    return TimedLegFuel(
        leg_id=reconciled.leg_id,
        before_start_tanks=reconciled.departure_tanks,
        takeoff_tanks=snapshot(takeoff),
        landing_tanks=snapshot(landing),
        after_shutdown_tanks=reconciled.arrival_tanks,
        before_start_fuel_kg=reconciled.departure_fuel_kg,
        takeoff_fuel_kg=takeoff_total,
        landing_fuel_kg=landing_total,
        after_shutdown_fuel_kg=reconciled.arrival_fuel_kg,
    )
