"""Convert UI loading inputs into validated flight-leg conditions."""

from math import isfinite

from flightops.operations.loading.leg_conditions import (
    CrewLoad,
    FuelStationLoad,
    LegLoadingConditions,
)


class LoadingInputError(ValueError):
    """A required loading input is missing or invalid."""


def required_weight(value, label: str) -> float:
    """Require an explicitly entered, nonnegative finite weight."""

    if value is None or isinstance(value, bool):
        raise LoadingInputError(f"{label} must be entered.")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise LoadingInputError(f"{label} must be numeric.") from exc

    if not isfinite(result) or result < 0:
        raise LoadingInputError(f"{label} must be finite and nonnegative.")

    return result


def build_leg_conditions(
    *,
    leg_uid: str,
    pilot_weight_kg,
    pilot_station_id: str,
    takeoff_fuel: dict[str, float | None],
    landing_fuel: dict[str, float | None],
) -> LegLoadingConditions:
    """Build one leg's loading conditions from explicit inputs.

    No aircraft weights, fuel quantities or station assignments
    are inferred by this service.
    """

    if not pilot_station_id:
        raise LoadingInputError("A pilot loading station must be selected.")

    pilot_weight = required_weight(
        pilot_weight_kg,
        "Pilot weight",
    )

    if not takeoff_fuel:
        raise LoadingInputError("No configured fuel stations are available.")

    if set(takeoff_fuel) != set(landing_fuel):
        raise LoadingInputError("Takeoff and landing fuel station sets differ.")

    departure = tuple(
        FuelStationLoad(
            station_id=station_id,
            weight_kg=required_weight(
                weight,
                f"Takeoff fuel at {station_id}",
            ),
        )
        for station_id, weight in takeoff_fuel.items()
    )

    arrival = tuple(
        FuelStationLoad(
            station_id=station_id,
            weight_kg=required_weight(
                landing_fuel[station_id],
                f"Landing fuel at {station_id}",
            ),
        )
        for station_id in takeoff_fuel
    )

    return LegLoadingConditions(
        leg_uid=leg_uid,
        crew=(
            CrewLoad(
                crew_id="PILOT_1",
                name="Pilot",
                station_id=pilot_station_id,
                weight_kg=pilot_weight,
            ),
        ),
        takeoff_fuel=departure,
        landing_fuel=arrival,
    )
