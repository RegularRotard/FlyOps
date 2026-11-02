"""Tests connecting operation leg IDs to flight-day fuel planning."""

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
from flightops.operations.services.unified_fuel_planning import (
    calculate_unified_fuel_plan,
)


def sample_configuration():
    """Fictional test aircraft fuel configuration."""

    return FuelPlanningConfiguration(
        fuel_type="Fictional test fuel",
        default_density_kg_per_litre=0.8,
        density_source_document_id="test-density",
        consumption_rates=[
            FuelConsumptionRate(
                phase=FuelPhase.FLIGHT,
                consumption_kg_per_hour=72.0,
                source_document_id="test-flight",
            ),
            FuelConsumptionRate(
                phase=FuelPhase.IDLE,
                consumption_kg_per_hour=24.0,
                source_document_id="test-idle",
            ),
        ],
    )


def planning_leg(
    leg_id,
    minutes,
    *,
    flight_type=FlightType.CHARTER,
    shutdown=True,
):
    return FlightPlanningLeg(
        leg_id=leg_id,
        flight_type=flight_type,
        planned_flight_minutes=minutes,
        scenic_block_minutes=(minutes if flight_type == FlightType.SCENIC else None),
        shutdown_after_leg=shutdown,
    )


def test_single_leg_integration():
    result = calculate_unified_fuel_plan(
        ("LEG-001",),
        (planning_leg("LEG-001", 45),),
        sample_configuration(),
    )

    assert len(result.legs) == 1
    assert result.legs[0].leg_id == "LEG-001"
    assert result.total_planned_fuel_kg == pytest.approx(58.8)


def test_multiple_leg_integration():
    result = calculate_unified_fuel_plan(
        ("LEG-001", "LEG-002"),
        (
            planning_leg("LEG-001", 15, shutdown=False),
            planning_leg("LEG-002", 30, shutdown=True),
        ),
        sample_configuration(),
    )

    assert len(result.legs) == 2
    assert result.total_flight_minutes == 45
    assert result.total_idle_minutes == 12


def test_missing_planning_leg_rejected():
    with pytest.raises(ValueError, match="match operation legs"):
        calculate_unified_fuel_plan(
            ("LEG-001", "LEG-002"),
            (planning_leg("LEG-001", 15),),
            sample_configuration(),
        )


def test_extra_planning_leg_rejected():
    with pytest.raises(ValueError, match="match operation legs"):
        calculate_unified_fuel_plan(
            ("LEG-001",),
            (
                planning_leg("LEG-001", 15),
                planning_leg("LEG-002", 30),
            ),
            sample_configuration(),
        )


def test_incorrect_leg_order_rejected():
    with pytest.raises(ValueError, match="including their order"):
        calculate_unified_fuel_plan(
            ("LEG-001", "LEG-002"),
            (
                planning_leg("LEG-002", 30),
                planning_leg("LEG-001", 15),
            ),
            sample_configuration(),
        )


def test_duplicate_operation_ids_rejected():
    with pytest.raises(ValueError, match="unique"):
        calculate_unified_fuel_plan(
            ("LEG-001", "LEG-001"),
            (
                planning_leg("LEG-001", 15),
                planning_leg("LEG-001", 30),
            ),
            sample_configuration(),
        )


def test_empty_operation_rejected():
    with pytest.raises(ValueError):
        calculate_unified_fuel_plan(
            (),
            (),
            sample_configuration(),
        )


def test_scenic_classification_preserved():
    result = calculate_unified_fuel_plan(
        ("LEG-001",),
        (
            planning_leg(
                "LEG-001",
                15,
                flight_type=FlightType.SCENIC,
            ),
        ),
        sample_configuration(),
    )

    assert result.legs[0].flight_type == FlightType.SCENIC


def test_ferry_classification_preserved():
    result = calculate_unified_fuel_plan(
        ("LEG-001",),
        (
            planning_leg(
                "LEG-001",
                45,
                flight_type=FlightType.FERRY,
            ),
        ),
        sample_configuration(),
    )

    assert result.legs[0].flight_type == FlightType.FERRY


def test_continuous_engine_running():
    result = calculate_unified_fuel_plan(
        ("LEG-001", "LEG-002"),
        (
            planning_leg("LEG-001", 15, shutdown=False),
            planning_leg("LEG-002", 30, shutdown=True),
        ),
        sample_configuration(),
    )

    assert result.legs[0].startup_minutes == 6
    assert result.legs[0].shutdown_minutes == 0

    assert result.legs[1].startup_minutes == 0
    assert result.legs[1].shutdown_minutes == 6


def test_final_engine_state_preserved():
    result = calculate_unified_fuel_plan(
        ("LEG-001",),
        (planning_leg("LEG-001", 15, shutdown=False),),
        sample_configuration(),
    )

    assert result.final_engine_running is True


def test_shutdown_between_flights():
    result = calculate_unified_fuel_plan(
        ("LEG-001", "LEG-002"),
        (
            planning_leg("LEG-001", 15, shutdown=True),
            planning_leg("LEG-002", 30, shutdown=True),
        ),
        sample_configuration(),
    )

    assert result.total_idle_minutes == 24
    assert result.total_planned_fuel_kg == pytest.approx(63.6)
