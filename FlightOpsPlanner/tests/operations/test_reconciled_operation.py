"""Tests for reconciled fuel integration with flight operations."""

import pytest

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
)
from flightops.operations.schemas.flight_planning import FlightType
from flightops.operations.services.automatic_fuel_reconciliation import (
    LegTankAllocation,
    TankQuantity,
    calculate_fuel_reconciliation,
)
from flightops.operations.services.reconciled_operation import (
    build_reconciled_operation,
)
from flightops.operations.services.unified_fuel_planning import (
    UnifiedFuelPlanningResult,
    UnifiedLegFuel,
)


def operation():
    """Create a fictional two-leg operation."""

    return FlightOperation(
        operation_id="OP-001",
        aircraft_profile_id="AIRCRAFT-001",
        configuration_revision_id="REV-001",
        legs=[
            FlightLeg(
                leg_id="LEG-1",
                sequence_number=1,
                departure=FlightLocation(
                    location_id="A",
                    name="Location A",
                ),
                destination=FlightLocation(
                    location_id="B",
                    name="Location B",
                ),
                fuel=LegFuelState(
                    tanks=[
                        LegFuelTank(
                            station_id="MAIN",
                            departure_fuel_kg=100,
                            planned_burn_kg=0,
                        ),
                        LegFuelTank(
                            station_id="AUX",
                            departure_fuel_kg=50,
                            planned_burn_kg=0,
                        ),
                    ],
                ),
            ),
            FlightLeg(
                leg_id="LEG-2",
                sequence_number=2,
                departure=FlightLocation(
                    location_id="B",
                    name="Location B",
                ),
                destination=FlightLocation(
                    location_id="C",
                    name="Location C",
                ),
                fuel=LegFuelState(
                    tanks=[
                        LegFuelTank(
                            station_id="MAIN",
                            departure_fuel_kg=100,
                            planned_burn_kg=0,
                        ),
                        LegFuelTank(
                            station_id="AUX",
                            departure_fuel_kg=50,
                            planned_burn_kg=0,
                        ),
                    ],
                ),
            ),
        ],
    )


def fuel_plan():
    """Create fictional planned fuel requirements."""

    return UnifiedFuelPlanningResult(
        legs=(
            UnifiedLegFuel(
                leg_id="LEG-1",
                flight_type=FlightType.SCENIC,
                planned_flight_minutes=15,
                startup_minutes=6,
                shutdown_minutes=0,
                additional_idle_minutes=0,
                planned_fuel_kg=20.4,
            ),
            UnifiedLegFuel(
                leg_id="LEG-2",
                flight_type=FlightType.CHARTER,
                planned_flight_minutes=30,
                startup_minutes=0,
                shutdown_minutes=6,
                additional_idle_minutes=0,
                planned_fuel_kg=38.4,
            ),
        ),
        total_flight_minutes=45,
        total_idle_minutes=12,
        total_planned_fuel_kg=58.8,
        final_engine_running=False,
    )


def allocations():
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


def integrated_result():
    original = operation()
    tank_allocations = allocations()

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan(),
        (
            TankQuantity("MAIN", 100),
            TankQuantity("AUX", 50),
        ),
        tank_allocations,
    )

    return build_reconciled_operation(
        original,
        reconciliation,
        tank_allocations,
    )


def test_reconciled_operation_contains_burn():
    result = integrated_result()

    assert result.operation.legs[0].fuel.planned_burn_kg == pytest.approx(20.4)


def test_arrival_fuel_is_automatic():
    result = integrated_result()

    assert result.operation.legs[0].fuel.arrival_fuel_kg == pytest.approx(129.6)


def test_second_leg_fuel_continuity():
    result = integrated_result()

    assert result.operation.legs[1].fuel.departure_fuel_kg == pytest.approx(129.6)


def test_final_arrival_fuel():
    result = integrated_result()

    assert result.operation.legs[-1].fuel.arrival_fuel_kg == pytest.approx(91.2)


def test_original_operation_is_unchanged():
    original = operation()

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan(),
        (
            TankQuantity("MAIN", 100),
            TankQuantity("AUX", 50),
        ),
        allocations(),
    )

    build_reconciled_operation(
        original,
        reconciliation,
        allocations(),
    )

    assert original.legs[0].fuel.planned_burn_kg == 0
    assert original.legs[1].fuel.planned_burn_kg == 0


def test_aircraft_revision_identity_preserved():
    result = integrated_result()

    assert result.operation.aircraft_profile_id == "AIRCRAFT-001"
    assert result.operation.configuration_revision_id == "REV-001"


def test_fuel_continuity_is_validated():
    result = integrated_result()

    assert len(result.fuel_continuity.transitions) == 1


def test_mismatched_leg_order_rejected():
    original = operation()

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan(),
        (
            TankQuantity("MAIN", 100),
            TankQuantity("AUX", 50),
        ),
        allocations(),
    )

    with pytest.raises(ValueError, match="match exactly"):
        build_reconciled_operation(
            original,
            reconciliation,
            tuple(reversed(allocations())),
        )


def test_refuelling_before_first_leg_rejected():
    original = operation()

    altered = (
        LegTankAllocation(
            leg_id="LEG-1",
            consumption=(TankQuantity("MAIN", 20.4),),
            refuel_before_leg=(TankQuantity("MAIN", 10),),
        ),
        allocations()[1],
    )

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan(),
        (
            TankQuantity("MAIN", 100),
            TankQuantity("AUX", 50),
        ),
        altered,
    )

    with pytest.raises(ValueError, match="before the first leg"):
        build_reconciled_operation(
            original,
            reconciliation,
            altered,
        )


def test_unknown_fuel_station_rejected():
    original = operation()

    original.legs[0].fuel.tanks[0].station_id = "UNKNOWN"

    reconciliation = calculate_fuel_reconciliation(
        fuel_plan(),
        (
            TankQuantity("MAIN", 100),
            TankQuantity("AUX", 50),
        ),
        allocations(),
    )

    with pytest.raises(ValueError, match="Fuel station mismatch"):
        build_reconciled_operation(
            original,
            reconciliation,
            allocations(),
        )
