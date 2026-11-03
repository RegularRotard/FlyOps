"""Fixed *planning-reference* fuel densities, kg/L at 15°C.

These are configurable development assumptions, not measured batch densities.
Do not treat this conversion as a certified aircraft W&B fuel density.
"""

from enum import StrEnum


class FuelGrade(StrEnum):
    JET_A1 = "Jet A-1"
    AVGAS = "AVGAS"


# Planning reference constants only; use documented/measured aircraft-specific
# values in any later operationally authorised workflow.
DENSITY_KG_PER_LITRE = {
    FuelGrade.JET_A1: 0.800,
    FuelGrade.AVGAS: 0.710,
}


def fuel_density_kg_per_litre(grade: FuelGrade | str) -> float:
    """Return the fixed planning density for an explicitly selected grade."""
    return DENSITY_KG_PER_LITRE[FuelGrade(grade)]
