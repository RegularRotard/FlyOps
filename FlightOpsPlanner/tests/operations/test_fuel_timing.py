"""Tests for takeoff and landing fuel timing."""

import pytest

from flightops.operations.services.automatic_fuel_reconciliation import (
    ReconciledLegFuel,
    TankQuantity,
)
from flightops.operations.services.fuel_timing import (
    TankFuelTiming,
    calculate_timed_leg_fuel,
)


def reconciled_leg():
    """Fictional single-tank flight consuming 40.8 kg."""

    return ReconciledLegFuel(
        leg_id="LEG-001",
        departure_tanks=(TankQuantity("MAIN", 120.0),),
        arrival_tanks=(TankQuantity("MAIN", 79.2),),
        departure_fuel_kg=120.0,
        consumed_fuel_kg=40.8,
        arrival_fuel_kg=79.2,
        refuel_before_leg_kg=0.0,
    )


def allocations():
    return (
        TankFuelTiming(
            tank_id="MAIN",
            before_takeoff_kg=2.4,
            airborne_kg=36.0,
            after_landing_kg=2.4,
        ),
    )


def calculate():
    return calculate_timed_leg_fuel(
        reconciled_leg(),
        allocations(),
        expected_before_takeoff_kg=2.4,
        expected_airborne_kg=36.0,
        expected_after_landing_kg=2.4,
    )


def test_fuel_before_start():
    assert calculate().before_start_fuel_kg == pytest.approx(120)


def test_takeoff_fuel_excludes_startup():
    assert calculate().takeoff_fuel_kg == pytest.approx(117.6)


def test_landing_fuel_excludes_shutdown():
    assert calculate().landing_fuel_kg == pytest.approx(81.6)


def test_after_shutdown_fuel():
    assert calculate().after_shutdown_fuel_kg == pytest.approx(79.2)


def test_takeoff_and_landing_are_different():
    result = calculate()

    assert result.takeoff_fuel_kg > result.landing_fuel_kg


def test_tank_quantities_are_preserved():
    result = calculate()

    assert result.takeoff_tanks[0].kilograms == pytest.approx(117.6)
    assert result.landing_tanks[0].kilograms == pytest.approx(81.6)


def test_consumption_mismatch_rejected():
    with pytest.raises(ValueError, match="phase consumption"):
        calculate_timed_leg_fuel(
            reconciled_leg(),
            allocations(),
            expected_before_takeoff_kg=3.0,
            expected_airborne_kg=36.0,
            expected_after_landing_kg=2.4,
        )


def test_unknown_tank_rejected():
    with pytest.raises(ValueError, match="match departure"):
        calculate_timed_leg_fuel(
            reconciled_leg(),
            (
                TankFuelTiming(
                    tank_id="UNKNOWN",
                    before_takeoff_kg=2.4,
                    airborne_kg=36,
                    after_landing_kg=2.4,
                ),
            ),
            expected_before_takeoff_kg=2.4,
            expected_airborne_kg=36,
            expected_after_landing_kg=2.4,
        )


def test_duplicate_tanks_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        calculate_timed_leg_fuel(
            reconciled_leg(),
            allocations() + allocations(),
            expected_before_takeoff_kg=4.8,
            expected_airborne_kg=72,
            expected_after_landing_kg=4.8,
        )


def test_negative_consumption_rejected():
    with pytest.raises(ValueError):
        TankFuelTiming(
            tank_id="MAIN",
            before_takeoff_kg=-1,
            airborne_kg=36,
            after_landing_kg=2.4,
        )


def test_nonfinite_consumption_rejected():
    with pytest.raises(ValueError):
        TankFuelTiming(
            tank_id="MAIN",
            before_takeoff_kg=float("inf"),
            airborne_kg=36,
            after_landing_kg=2.4,
        )


def test_insufficient_fuel_rejected():
    """Reject overdrawing a tank even when total aircraft fuel is sufficient."""

    reconciled = ReconciledLegFuel(
        leg_id="LEG-001",
        departure_tanks=(
            TankQuantity("MAIN", 10.0),
            TankQuantity("AUX", 110.0),
        ),
        arrival_tanks=(
            TankQuantity("MAIN", 10.0),
            TankQuantity("AUX", 69.2),
        ),
        departure_fuel_kg=120.0,
        consumed_fuel_kg=40.8,
        arrival_fuel_kg=79.2,
        refuel_before_leg_kg=0.0,
    )

    # Total consumption is correctly 40.8 kg.
    #
    # However, the allocation attempts to consume
    # 12 kg from MAIN, which contains only 10 kg.

    allocations = (
        TankFuelTiming(
            tank_id="MAIN",
            before_takeoff_kg=12.0,
            airborne_kg=0.0,
            after_landing_kg=0.0,
        ),
        TankFuelTiming(
            tank_id="AUX",
            before_takeoff_kg=0.0,
            airborne_kg=26.4,
            after_landing_kg=2.4,
        ),
    )

    with pytest.raises(ValueError, match="Insufficient fuel"):
        calculate_timed_leg_fuel(
            reconciled,
            allocations,
            expected_before_takeoff_kg=12.0,
            expected_airborne_kg=26.4,
            expected_after_landing_kg=2.4,
        )
