"""Tests for simultaneous fuel quantity display."""

import pytest

from flightops.fuel.display import (
    FuelDisplayBasis,
    display_fuel,
)


def test_fuel_display_all_three_units():
    basis = FuelDisplayBasis(
        density_kg_per_litre=0.8,
        consumption_kg_per_hour=72.0,
    )

    result = display_fuel(120.0, basis)

    assert result.kilograms == pytest.approx(120.0)
    assert result.litres == pytest.approx(150.0)
    assert result.minutes == pytest.approx(100.0)


def test_fuel_burn_duration():
    basis = FuelDisplayBasis(
        density_kg_per_litre=0.8,
        consumption_kg_per_hour=72.0,
    )

    result = display_fuel(30.0, basis)

    assert result.litres == pytest.approx(37.5)
    assert result.minutes == pytest.approx(25.0)


def test_missing_density_does_not_invent_litres():
    basis = FuelDisplayBasis(
        consumption_kg_per_hour=72.0,
    )

    result = display_fuel(120.0, basis)

    assert result.litres is None
    assert result.minutes == pytest.approx(100.0)


def test_missing_consumption_does_not_invent_minutes():
    basis = FuelDisplayBasis(
        density_kg_per_litre=0.8,
    )

    result = display_fuel(120.0, basis)

    assert result.litres == pytest.approx(150.0)
    assert result.minutes is None


def test_missing_conversion_data():
    result = display_fuel(
        120.0,
        FuelDisplayBasis(),
    )

    assert result.formatted == ("120.0 kg / N/A L / N/A min")


def test_zero_fuel():
    basis = FuelDisplayBasis(
        density_kg_per_litre=0.8,
        consumption_kg_per_hour=72.0,
    )

    result = display_fuel(0.0, basis)

    assert result.kilograms == 0
    assert result.litres == 0
    assert result.minutes == 0


def test_negative_fuel_rejected():
    with pytest.raises(ValueError):
        display_fuel(
            -10.0,
            FuelDisplayBasis(),
        )


def test_zero_density_rejected():
    with pytest.raises(ValueError):
        FuelDisplayBasis(
            density_kg_per_litre=0,
        )


def test_negative_consumption_rejected():
    with pytest.raises(ValueError):
        FuelDisplayBasis(
            consumption_kg_per_hour=-50,
        )


def test_nonfinite_fuel_rejected():
    with pytest.raises(ValueError):
        display_fuel(
            float("nan"),
            FuelDisplayBasis(),
        )
