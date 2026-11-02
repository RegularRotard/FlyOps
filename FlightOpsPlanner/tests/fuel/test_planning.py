"""Tests for simplified flight and idle fuel calculations."""

import pytest

from flightops.fuel.planning import (
    FuelPlanningInput,
    calculate_planned_fuel,
)
from tests.fuel.test_configuration import sample_configuration


def test_flight_fuel_calculation():
    result = calculate_planned_fuel(
        FuelPlanningInput(
            flight_minutes=45,
            idle_minutes=0,
        ),
        sample_configuration(),
    )

    assert result.flight_fuel.kilograms == pytest.approx(54.0)


def test_idle_fuel_calculation():
    result = calculate_planned_fuel(
        FuelPlanningInput(
            flight_minutes=0,
            idle_minutes=10,
        ),
        sample_configuration(),
    )

    assert result.idle_fuel.kilograms == pytest.approx(4.0)


def test_combined_fuel_calculation():
    result = calculate_planned_fuel(
        FuelPlanningInput(
            flight_minutes=45,
            idle_minutes=10,
        ),
        sample_configuration(),
    )

    assert result.total_fuel.kilograms == pytest.approx(58.0)


def test_fuel_volume_conversion():
    result = calculate_planned_fuel(
        FuelPlanningInput(45, 10),
        sample_configuration(),
    )

    assert result.total_fuel.litres == pytest.approx(72.5)


def test_flight_equivalent_minutes():
    result = calculate_planned_fuel(
        FuelPlanningInput(45, 10),
        sample_configuration(),
    )

    assert result.total_fuel.minutes == pytest.approx(58.0 / 72.0 * 60.0)


def test_idle_time_not_assumed_to_be_flight_time():
    result = calculate_planned_fuel(
        FuelPlanningInput(45, 10),
        sample_configuration(),
    )

    assert result.total_duration_minutes == pytest.approx(55.0)

    assert result.total_fuel.minutes != pytest.approx(55.0)


def test_zero_duration():
    result = calculate_planned_fuel(
        FuelPlanningInput(0, 0),
        sample_configuration(),
    )

    assert result.total_fuel.kilograms == 0


def test_negative_duration_rejected():
    with pytest.raises(ValueError):
        FuelPlanningInput(
            flight_minutes=-1,
            idle_minutes=0,
        )


def test_nonfinite_duration_rejected():
    with pytest.raises(ValueError):
        FuelPlanningInput(
            flight_minutes=float("nan"),
            idle_minutes=0,
        )


def test_flight_rate_override():
    result = calculate_planned_fuel(
        FuelPlanningInput(60, 0),
        sample_configuration(),
        flight_rate_override_kg_per_hour=80.0,
    )

    assert result.total_fuel.kilograms == pytest.approx(80.0)


def test_idle_rate_override():
    result = calculate_planned_fuel(
        FuelPlanningInput(0, 60),
        sample_configuration(),
        idle_rate_override_kg_per_hour=30.0,
    )

    assert result.total_fuel.kilograms == pytest.approx(30.0)


def test_density_override():
    result = calculate_planned_fuel(
        FuelPlanningInput(45, 10),
        sample_configuration(),
        density_override_kg_per_litre=0.75,
    )

    assert result.total_fuel.kilograms == pytest.approx(58.0)
    assert result.total_fuel.litres == pytest.approx(58.0 / 0.75)


def test_invalid_override_rejected():
    with pytest.raises(ValueError):
        calculate_planned_fuel(
            FuelPlanningInput(45, 10),
            sample_configuration(),
            flight_rate_override_kg_per_hour=0,
        )


def test_configuration_is_not_modified_by_override():
    configuration = sample_configuration()

    calculate_planned_fuel(
        FuelPlanningInput(60, 0),
        configuration,
        flight_rate_override_kg_per_hour=85.0,
    )

    assert configuration.rate_for_phase("flight").consumption_kg_per_hour == 72.0
