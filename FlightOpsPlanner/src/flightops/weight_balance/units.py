"""Unit conversions for aircraft weight and balance calculations."""

from enum import StrEnum
from math import isfinite


class MassUnit(StrEnum):
    KG = "kg"
    LB = "lb"


class LengthUnit(StrEnum):
    MM = "mm"
    CM = "cm"
    IN = "in"
    FT = "ft"


class VolumeUnit(StrEnum):
    L = "L"
    US_GAL = "us_gal"
    IMP_GAL = "imp_gal"


MASS_TO_KG = {
    MassUnit.KG: 1.0,
    MassUnit.LB: 0.45359237,
}

LENGTH_TO_MM = {
    LengthUnit.MM: 1.0,
    LengthUnit.CM: 10.0,
    LengthUnit.IN: 25.4,
    LengthUnit.FT: 304.8,
}

VOLUME_TO_L = {
    VolumeUnit.L: 1.0,
    VolumeUnit.US_GAL: 3.785411784,
    VolumeUnit.IMP_GAL: 4.54609,
}


def _convert(value, from_unit, to_unit, factors):
    """Convert between units of the same physical dimension."""

    if not isfinite(value):
        raise ValueError("Measurement must be finite.")

    try:
        result = value * factors[from_unit] / factors[to_unit]
    except KeyError as exc:
        raise ValueError(f"Unsupported unit: {exc}") from exc

    if not isfinite(result):
        raise ValueError("Unit conversion produced a nonfinite result.")

    return result


def convert_mass(
    value: float,
    from_unit: MassUnit,
    to_unit: MassUnit,
) -> float:
    return _convert(value, from_unit, to_unit, MASS_TO_KG)


def convert_length(
    value: float,
    from_unit: LengthUnit,
    to_unit: LengthUnit,
) -> float:
    return _convert(value, from_unit, to_unit, LENGTH_TO_MM)


def convert_volume(
    value: float,
    from_unit: VolumeUnit,
    to_unit: VolumeUnit,
) -> float:
    return _convert(value, from_unit, to_unit, VOLUME_TO_L)


def convert_moment(
    value: float,
    mass_from: MassUnit,
    length_from: LengthUnit,
    mass_to: MassUnit,
    length_to: LengthUnit,
) -> float:
    """Convert moments between mass-length unit combinations."""

    if not isfinite(value):
        raise ValueError("Moment must be finite.")

    try:
        result = (
            value
            * MASS_TO_KG[mass_from]
            * LENGTH_TO_MM[length_from]
            / MASS_TO_KG[mass_to]
            / LENGTH_TO_MM[length_to]
        )
    except KeyError as exc:
        raise ValueError(f"Unsupported unit: {exc}") from exc

    if not isfinite(result):
        raise ValueError("Moment conversion produced a nonfinite result.")

    return result


def fuel_volume_to_mass(
    volume: float,
    volume_unit: VolumeUnit,
    density_kg_per_l: float,
    mass_unit: MassUnit = MassUnit.KG,
) -> float:
    """Convert fuel volume to mass using an explicitly supplied density."""

    if not isfinite(density_kg_per_l) or density_kg_per_l <= 0:
        raise ValueError("Fuel density must be positive and finite.")

    if not isfinite(volume) or volume < 0:
        raise ValueError("Fuel volume must be non-negative and finite.")

    litres = convert_volume(volume, volume_unit, VolumeUnit.L)
    mass_kg = litres * density_kg_per_l

    if not isfinite(mass_kg):
        raise ValueError("Fuel mass calculation produced a nonfinite result.")

    return convert_mass(mass_kg, MassUnit.KG, mass_unit)
