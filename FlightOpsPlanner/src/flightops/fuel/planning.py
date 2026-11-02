"""Flight and idle fuel planning.

Calculations are independent of aircraft W&B and fuel continuity.

Results are planning estimates, not fuel-release approval.
"""

from dataclasses import dataclass
from math import isfinite

from flightops.fuel.configuration import (
    FuelPhase,
    FuelPlanningConfiguration,
)
from flightops.fuel.display import FuelDisplay, FuelDisplayBasis, display_fuel


@dataclass(frozen=True)
class FuelPlanningInput:
    """Planned airborne and ground-idle durations."""

    flight_minutes: float
    idle_minutes: float

    def __post_init__(self):
        for name, value in (
            ("Flight minutes", self.flight_minutes),
            ("Idle minutes", self.idle_minutes),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")


@dataclass(frozen=True)
class FuelPlanningResult:
    """Calculated flight, idle and total fuel requirements."""

    flight_minutes: float
    idle_minutes: float

    flight_consumption_kg_per_hour: float
    idle_consumption_kg_per_hour: float

    flight_fuel: FuelDisplay
    idle_fuel: FuelDisplay
    total_fuel: FuelDisplay

    density_kg_per_litre: float

    @property
    def total_duration_minutes(self) -> float:
        return self.flight_minutes + self.idle_minutes


def calculate_planned_fuel(
    planning: FuelPlanningInput,
    configuration: FuelPlanningConfiguration,
    *,
    density_override_kg_per_litre: float | None = None,
    flight_rate_override_kg_per_hour: float | None = None,
    idle_rate_override_kg_per_hour: float | None = None,
) -> FuelPlanningResult:
    """Calculate fuel for planned flight and idle durations.

    Optional overrides apply only to this calculation.
    They do not modify the aircraft's configuration.
    """

    configured_flight_rate = configuration.rate_for_phase(
        FuelPhase.FLIGHT
    ).consumption_kg_per_hour

    configured_idle_rate = configuration.rate_for_phase(
        FuelPhase.IDLE
    ).consumption_kg_per_hour

    flight_rate = (
        flight_rate_override_kg_per_hour
        if flight_rate_override_kg_per_hour is not None
        else configured_flight_rate
    )

    idle_rate = (
        idle_rate_override_kg_per_hour
        if idle_rate_override_kg_per_hour is not None
        else configured_idle_rate
    )

    density = (
        density_override_kg_per_litre
        if density_override_kg_per_litre is not None
        else configuration.default_density_kg_per_litre
    )

    # Validate all supplied planning assumptions.
    basis = FuelDisplayBasis(
        density_kg_per_litre=density,
        consumption_kg_per_hour=flight_rate,
    )

    FuelDisplayBasis(
        consumption_kg_per_hour=idle_rate,
    )

    flight_kg = planning.flight_minutes * flight_rate / 60.0
    idle_kg = planning.idle_minutes * idle_rate / 60.0
    total_kg = flight_kg + idle_kg

    if not all(isfinite(value) for value in (flight_kg, idle_kg, total_kg)):
        raise ValueError("Calculated fuel requirement is not finite.")

    return FuelPlanningResult(
        flight_minutes=planning.flight_minutes,
        idle_minutes=planning.idle_minutes,
        flight_consumption_kg_per_hour=flight_rate,
        idle_consumption_kg_per_hour=idle_rate,
        flight_fuel=display_fuel(
            flight_kg,
            basis,
        ),
        idle_fuel=display_fuel(
            idle_kg,
            FuelDisplayBasis(
                density_kg_per_litre=density,
            ),
        ),
        total_fuel=display_fuel(
            total_kg,
            basis,
        ),
        density_kg_per_litre=density,
    )
