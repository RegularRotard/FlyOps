"""Tests for flight classifications and engine-cycle fuel planning."""

import pytest
from pydantic import ValidationError

from flightops.fuel.configuration import (
    FuelConsumptionRate,
    FuelPhase,
    FuelPlanningConfiguration,
)
from flightops.operations.schemas.flight_planning import (
    FlightPlanningLeg,
    FlightType,
)
from flightops.operations.services.flight_day_fuel import (
    EngineCycleAllowance,
    calculate_flight_day_fuel,
)


def sample_configuration():
    """Use fictional consumption figures for isolated tests."""

    return FuelPlanningConfiguration(
        fuel_type="Fictional test fuel",
        default_density_kg_per_litre=0.8,
        density_source_document_id="test-density-source",
        consumption_rates=[
            FuelConsumptionRate(
                phase=FuelPhase.FLIGHT,
                consumption_kg_per_hour=72.0,
                source_document_id="test-flight-source",
            ),
            FuelConsumptionRate(
                phase=FuelPhase.IDLE,
                consumption_kg_per_hour=24.0,
                source_document_id="test-idle-source",
            ),
        ],
    )


def make_leg(
    number,
    *,
    flight_type=FlightType.CHARTER,
    minutes=30,
    shutdown=True,
    additional_idle=0,
):
    """Create a fictional flight leg."""

    return FlightPlanningLeg(
        leg_id=f"leg-{number}",
        flight_type=flight_type,
        planned_flight_minutes=minutes,
        shutdown_after_leg=shutdown,
        additional_idle_minutes=additional_idle,
        scenic_block_minutes=(minutes if flight_type == FlightType.SCENIC else None),
    )


def test_single_flight_includes_twelve_minutes_idle():
    result = calculate_flight_day_fuel(
        (make_leg(1),),
        sample_configuration(),
    )

    assert result.total_idle_minutes == pytest.approx(12)


def test_startup_allowance_is_six_minutes():
    result = calculate_flight_day_fuel(
        (make_leg(1),),
        sample_configuration(),
    )

    assert result.legs[0].startup_minutes == pytest.approx(6)


def test_shutdown_allowance_is_six_minutes():
    result = calculate_flight_day_fuel(
        (make_leg(1),),
        sample_configuration(),
    )

    assert result.legs[0].shutdown_minutes == pytest.approx(6)


def test_continuous_engine_operation_avoids_extra_cycle():
    result = calculate_flight_day_fuel(
        (
            make_leg(1, shutdown=False),
            make_leg(2, shutdown=True),
        ),
        sample_configuration(),
    )

    assert result.total_idle_minutes == pytest.approx(12)

    assert result.legs[0].startup_minutes == pytest.approx(6)
    assert result.legs[0].shutdown_minutes == 0

    assert result.legs[1].startup_minutes == 0
    assert result.legs[1].shutdown_minutes == pytest.approx(6)


def test_shutdown_between_flights_requires_restart():
    result = calculate_flight_day_fuel(
        (
            make_leg(1, shutdown=True),
            make_leg(2, shutdown=True),
        ),
        sample_configuration(),
    )

    assert result.total_idle_minutes == pytest.approx(24)
    assert result.legs[1].startup_required


def test_additional_idle_time_increases_total():
    result = calculate_flight_day_fuel(
        (make_leg(1, additional_idle=10),),
        sample_configuration(),
    )

    assert result.total_idle_minutes == pytest.approx(22)


def test_fifteen_minute_scenic_flight():
    result = calculate_flight_day_fuel(
        (
            make_leg(
                1,
                flight_type=FlightType.SCENIC,
                minutes=15,
            ),
        ),
        sample_configuration(),
    )

    assert result.total_flight_minutes == 15


def test_thirty_minute_scenic_flight():
    result = calculate_flight_day_fuel(
        (
            make_leg(
                1,
                flight_type=FlightType.SCENIC,
                minutes=30,
            ),
        ),
        sample_configuration(),
    )

    assert result.total_flight_minutes == 30


def test_unsupported_scenic_duration_rejected():
    with pytest.raises(ValidationError):
        make_leg(
            1,
            flight_type=FlightType.SCENIC,
            minutes=20,
        )


def test_ferry_flight_supported():
    result = calculate_flight_day_fuel(
        (
            make_leg(
                1,
                flight_type=FlightType.FERRY,
                minutes=45,
            ),
        ),
        sample_configuration(),
    )

    assert result.total_flight_minutes == 45


def test_single_flight_fuel_calculation():
    result = calculate_flight_day_fuel(
        (make_leg(1, minutes=45),),
        sample_configuration(),
    )

    # Flight: 45 min x 72 kg/h = 54 kg
    # Startup: 6 min x 24 kg/h = 2.4 kg
    # Shutdown: 6 min x 24 kg/h = 2.4 kg
    # Total: 58.8 kg

    assert result.total_fuel_kg == pytest.approx(58.8)


def test_two_flights_with_continuous_engine():
    result = calculate_flight_day_fuel(
        (
            make_leg(1, minutes=15, shutdown=False),
            make_leg(2, minutes=30, shutdown=True),
        ),
        sample_configuration(),
    )

    # 45 flight minutes = 54 kg
    # 12 idle minutes = 4.8 kg

    assert result.total_fuel_kg == pytest.approx(58.8)


def test_two_flights_with_shutdown_between():
    result = calculate_flight_day_fuel(
        (
            make_leg(1, minutes=15, shutdown=True),
            make_leg(2, minutes=30, shutdown=True),
        ),
        sample_configuration(),
    )

    # 45 flight minutes = 54 kg
    # 24 idle minutes = 9.6 kg

    assert result.total_fuel_kg == pytest.approx(63.6)


def test_duplicate_leg_ids_rejected():
    with pytest.raises(ValueError, match="unique"):
        calculate_flight_day_fuel(
            (
                make_leg(1),
                make_leg(1),
            ),
            sample_configuration(),
        )


def test_empty_flight_day_rejected():
    with pytest.raises(ValueError):
        calculate_flight_day_fuel(
            (),
            sample_configuration(),
        )


def test_custom_engine_allowances():
    result = calculate_flight_day_fuel(
        (make_leg(1),),
        sample_configuration(),
        allowance=EngineCycleAllowance(
            startup_minutes=4,
            shutdown_minutes=2,
        ),
    )

    assert result.total_idle_minutes == pytest.approx(6)


def test_negative_engine_allowance_rejected():
    with pytest.raises(ValueError):
        EngineCycleAllowance(
            startup_minutes=-1,
            shutdown_minutes=6,
        )


def test_nonfinite_engine_allowance_rejected():
    with pytest.raises(ValueError):
        EngineCycleAllowance(
            startup_minutes=float("inf"),
            shutdown_minutes=6,
        )


def test_engine_already_running_at_start():
    result = calculate_flight_day_fuel(
        (make_leg(1),),
        sample_configuration(),
        engine_running_at_start=True,
    )

    assert result.legs[0].startup_minutes == 0
    assert result.legs[0].shutdown_minutes == pytest.approx(6)
    assert result.total_idle_minutes == pytest.approx(6)
