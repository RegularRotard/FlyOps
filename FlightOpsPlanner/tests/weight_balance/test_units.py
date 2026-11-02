"""Tests for aircraft measurement unit conversions."""

import pytest

from flightops.weight_balance.units import (
    LengthUnit,
    MassUnit,
    VolumeUnit,
    convert_length,
    convert_mass,
    convert_moment,
    convert_volume,
    fuel_volume_to_mass,
)


def test_pounds_to_kilograms():
    assert convert_mass(100, MassUnit.LB, MassUnit.KG) == pytest.approx(45.359237)


def test_kilograms_to_pounds():
    assert convert_mass(100, MassUnit.KG, MassUnit.LB) == pytest.approx(220.462262)


def test_inches_to_millimetres():
    assert convert_length(10, LengthUnit.IN, LengthUnit.MM) == pytest.approx(254)


def test_centimetres_to_millimetres():
    assert convert_length(25, LengthUnit.CM, LengthUnit.MM) == pytest.approx(250)


def test_feet_to_millimetres():
    assert convert_length(1, LengthUnit.FT, LengthUnit.MM) == pytest.approx(304.8)


def test_us_gallons_to_litres():
    assert convert_volume(10, VolumeUnit.US_GAL, VolumeUnit.L) == pytest.approx(
        37.85411784
    )


def test_imperial_gallons_to_litres():
    assert convert_volume(10, VolumeUnit.IMP_GAL, VolumeUnit.L) == pytest.approx(
        45.4609
    )


def test_moment_conversion():
    result = convert_moment(
        1000,
        MassUnit.LB,
        LengthUnit.IN,
        MassUnit.KG,
        LengthUnit.MM,
    )

    assert result == pytest.approx(11521.246198)


def test_fuel_volume_to_mass():
    result = fuel_volume_to_mass(
        volume=100,
        volume_unit=VolumeUnit.L,
        density_kg_per_l=0.72,
    )

    assert result == pytest.approx(72)


def test_invalid_fuel_density():
    with pytest.raises(ValueError):
        fuel_volume_to_mass(
            100,
            VolumeUnit.L,
            density_kg_per_l=0,
        )


def test_negative_fuel_volume():
    with pytest.raises(ValueError):
        fuel_volume_to_mass(
            -10,
            VolumeUnit.L,
            density_kg_per_l=0.72,
        )
