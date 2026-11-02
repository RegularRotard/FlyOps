"""Tests for automatic per-leg fuel reconciliation."""

import pytest

from flightops.fuel.configuration import (
    FuelConsumptionRate,
    FuelPhase,
    FuelPlanningConfiguration,
)
from flightops.operations.schemas.flight_planning import (
    FlightPlanningLeg,
    FlightType,
)
from flightops.operations.services.automatic_fuel_reconciliation import (
    LegTankAllocation,
    TankQuantity,
    calculate_fuel_reconciliation,
)
from flightops.operations.services.unified_fuel_planning import (
    calculate_unified_fuel_plan,
)


def configuration():
    return FuelPlanningConfiguration(
        fuel_type="Fictional test fuel",
        default_density_kg_per_litre=0.8,
        density_source_document_id="test-density",
        consumption_rates=[
            FuelConsumptionRate(
                phase=FuelPhase.FLIGHT,
                consumption_kg_per_hour=72,
                source_document_id="test-flight",
            ),
            FuelConsumptionRate(
                phase=FuelPhase.IDLE,
                consumption_kg_per_hour=24,
                source_document_id="test-idle",
            ),
        ],
    )


def fuel_plan():
    return calculate_unified_fuel_plan(
        ("LEG-1", "LEG-2"),
        (
            FlightPlanningLeg(
                leg_id="LEG-1",
                flight_type=FlightType.SCENIC,
                planned_flight_minutes=15,
                scenic_block_minutes=15,
                shutdown_after_leg=False,
            ),
            FlightPlanningLeg(
                leg_id="LEG-2",
                flight_type=FlightType.CHARTER,
                planned_flight_minutes=30,
                shutdown_after_leg=True,
            ),
        ),
        configuration(),
    )


def initial_tanks():
    return (
        TankQuantity("MAIN", 100),
        TankQuantity("AUX", 50),
    )


def allocations():
    # LEG-1: 15 min flight + 6 min startup = 20.4 kg
    # LEG-2: 30 min flight + 6 min shutdown = 38.4 kg
    return (
        LegTankAllocation(
            leg_id="LEG-1",
            consumption=(TankQuantity("MAIN", 20.4),),
        ),
        LegTankAllocation(
            leg_id="LEG-2",
            consumption=(
                TankQuantity("MAIN", 30),
                TankQuantity("AUX", 8.4),
            ),
        ),
    )


def test_two_leg_reconciliation():
    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        allocations(),
    )

    assert len(result.legs) == 2
    assert result.total_consumption_kg == pytest.approx(58.8)
    assert result.final_fuel_kg == pytest.approx(91.2)


def test_first_leg_departure_fuel():
    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        allocations(),
    )

    assert result.legs[0].departure_fuel_kg == pytest.approx(150)


def test_second_leg_departure_equals_first_arrival():
    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        allocations(),
    )

    assert result.legs[1].departure_fuel_kg == pytest.approx(
        result.legs[0].arrival_fuel_kg
    )


def test_tank_quantities_preserved():
    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        allocations(),
    )

    final_tanks = {
        tank.tank_id: tank.kilograms for tank in result.legs[-1].arrival_tanks
    }

    assert final_tanks["MAIN"] == pytest.approx(49.6)
    assert final_tanks["AUX"] == pytest.approx(41.6)


def test_refuelling_before_second_leg():
    original = allocations()

    with_refuel = (
        original[0],
        LegTankAllocation(
            leg_id="LEG-2",
            consumption=original[1].consumption,
            refuel_before_leg=(TankQuantity("MAIN", 20),),
        ),
    )

    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        with_refuel,
    )

    assert result.total_refuel_kg == pytest.approx(20)
    assert result.final_fuel_kg == pytest.approx(111.2)


def test_consumption_mismatch_rejected():
    incorrect = (
        LegTankAllocation(
            leg_id="LEG-1",
            consumption=(TankQuantity("MAIN", 10),),
        ),
        allocations()[1],
    )

    with pytest.raises(ValueError, match="does not match"):
        calculate_fuel_reconciliation(
            fuel_plan(),
            initial_tanks(),
            incorrect,
        )


def test_unknown_tank_rejected():
    incorrect = (
        LegTankAllocation(
            leg_id="LEG-1",
            consumption=(TankQuantity("UNKNOWN", 20.4),),
        ),
        allocations()[1],
    )

    with pytest.raises(ValueError, match="Unknown tank"):
        calculate_fuel_reconciliation(
            fuel_plan(),
            initial_tanks(),
            incorrect,
        )


def test_duplicate_tank_rejected():
    with pytest.raises(ValueError, match="Duplicate tank"):
        calculate_fuel_reconciliation(
            fuel_plan(),
            (
                TankQuantity("MAIN", 100),
                TankQuantity("MAIN", 50),
            ),
            allocations(),
        )


def test_negative_tank_quantity_rejected():
    with pytest.raises(ValueError):
        TankQuantity("MAIN", -10)


def test_nonfinite_tank_quantity_rejected():
    with pytest.raises(ValueError):
        TankQuantity("MAIN", float("inf"))


def test_wrong_leg_order_rejected():
    with pytest.raises(ValueError, match="same order"):
        calculate_fuel_reconciliation(
            fuel_plan(),
            initial_tanks(),
            tuple(reversed(allocations())),
        )


def test_insufficient_tank_fuel_rejected():
    with pytest.raises(ValueError, match="Insufficient fuel"):
        calculate_fuel_reconciliation(
            fuel_plan(),
            (
                TankQuantity("MAIN", 10),
                TankQuantity("AUX", 100),
            ),
            allocations(),
        )


def test_negative_refuel_rejected():
    with pytest.raises(ValueError):
        TankQuantity("MAIN", -5)


def test_operation_mass_balance():
    result = calculate_fuel_reconciliation(
        fuel_plan(),
        initial_tanks(),
        allocations(),
    )

    assert (
        result.initial_fuel_kg + result.total_refuel_kg - result.total_consumption_kg
    ) == pytest.approx(result.final_fuel_kg)
