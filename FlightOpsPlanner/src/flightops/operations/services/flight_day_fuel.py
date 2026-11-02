"""Flight-day fuel planning with engine startup and shutdown allowances.

Default startup allowance: 6 minutes.
Default shutdown allowance: 6 minutes.

Both allowances use the configured idle fuel-consumption rate.

Calculations are planning estimates, not flight-release approval.
"""

from dataclasses import dataclass
from math import isfinite

from flightops.fuel.configuration import FuelPlanningConfiguration
from flightops.fuel.planning import (
    FuelPlanningInput,
    FuelPlanningResult,
    calculate_planned_fuel,
)
from flightops.operations.schemas.flight_planning import FlightPlanningLeg


@dataclass(frozen=True)
class EngineCycleAllowance:
    """Engine startup and shutdown allowances in minutes."""

    startup_minutes: float = 6.0
    shutdown_minutes: float = 6.0

    def __post_init__(self):
        """Validate engine-cycle allowances."""

        for name, value in (
            ("Startup minutes", self.startup_minutes),
            ("Shutdown minutes", self.shutdown_minutes),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")


@dataclass(frozen=True)
class FlightDayLegFuelResult:
    """Fuel-planning result for one flight leg."""

    leg_id: str

    startup_required: bool
    shutdown_required: bool

    startup_minutes: float
    shutdown_minutes: float
    additional_idle_minutes: float

    fuel: FuelPlanningResult

    @property
    def total_idle_minutes(self) -> float:
        """Total idle allowance assigned to this flight leg."""

        return (
            self.startup_minutes + self.shutdown_minutes + self.additional_idle_minutes
        )


@dataclass(frozen=True)
class FlightDayFuelResult:
    """Combined fuel-planning results for multiple flight legs."""

    legs: tuple[FlightDayLegFuelResult, ...]

    total_flight_minutes: float
    total_idle_minutes: float
    total_fuel_kg: float


def calculate_flight_day_fuel(
    legs: tuple[FlightPlanningLeg, ...],
    configuration: FuelPlanningConfiguration,
    *,
    allowance: EngineCycleAllowance | None = None,
    engine_running_at_start: bool = False,
) -> FlightDayFuelResult:
    """Calculate fuel using flight time and engine-running idle time.

    Startup is included whenever the preceding engine state is stopped.

    Shutdown is included whenever shutdown_after_leg is True.

    Additional idle time is supplied explicitly by the planner.
    """

    if not legs:
        raise ValueError("At least one flight leg is required.")

    leg_ids = [leg.leg_id for leg in legs]

    if len(leg_ids) != len(set(leg_ids)):
        raise ValueError("Flight leg IDs must be unique.")

    if allowance is None:
        allowance = EngineCycleAllowance()

    engine_running = engine_running_at_start

    results = []

    for leg in legs:
        startup_required = not engine_running

        shutdown_required = leg.shutdown_after_leg

        startup_minutes = allowance.startup_minutes if startup_required else 0.0

        shutdown_minutes = allowance.shutdown_minutes if shutdown_required else 0.0

        total_idle_minutes = (
            startup_minutes + shutdown_minutes + leg.additional_idle_minutes
        )

        fuel = calculate_planned_fuel(
            FuelPlanningInput(
                flight_minutes=leg.planned_flight_minutes,
                idle_minutes=total_idle_minutes,
            ),
            configuration,
        )

        results.append(
            FlightDayLegFuelResult(
                leg_id=leg.leg_id,
                startup_required=startup_required,
                shutdown_required=shutdown_required,
                startup_minutes=startup_minutes,
                shutdown_minutes=shutdown_minutes,
                additional_idle_minutes=leg.additional_idle_minutes,
                fuel=fuel,
            )
        )

        # Determine the engine state before the next flight.
        engine_running = not shutdown_required

    total_flight_minutes = sum(result.fuel.flight_minutes for result in results)

    total_idle_minutes = sum(result.total_idle_minutes for result in results)

    total_fuel_kg = sum(result.fuel.total_fuel.kilograms for result in results)

    if not all(
        isfinite(value)
        for value in (
            total_flight_minutes,
            total_idle_minutes,
            total_fuel_kg,
        )
    ):
        raise ValueError("Flight-day fuel totals must be finite.")

    return FlightDayFuelResult(
        legs=tuple(results),
        total_flight_minutes=total_flight_minutes,
        total_idle_minutes=total_idle_minutes,
        total_fuel_kg=total_fuel_kg,
    )
