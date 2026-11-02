"""Numerical overflow tests for aircraft W&B unit conversions."""

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


def test_mass_conversion_overflow_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        convert_mass(1e308, MassUnit.KG, MassUnit.LB)


def test_length_conversion_overflow_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        convert_length(1e308, LengthUnit.FT, LengthUnit.MM)


def test_volume_conversion_overflow_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        convert_volume(1e308, VolumeUnit.IMP_GAL, VolumeUnit.L)


def test_moment_conversion_overflow_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        convert_moment(
            1e308,
            MassUnit.KG,
            LengthUnit.FT,
            MassUnit.KG,
            LengthUnit.MM,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_moment_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        convert_moment(
            value,
            MassUnit.KG,
            LengthUnit.MM,
            MassUnit.KG,
            LengthUnit.MM,
        )


def test_fuel_mass_overflow_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        fuel_volume_to_mass(
            1e308,
            VolumeUnit.L,
            density_kg_per_l=10,
        )


def test_normal_conversion_still_works():
    assert convert_mass(100, MassUnit.KG, MassUnit.LB) == pytest.approx(220.462262)
