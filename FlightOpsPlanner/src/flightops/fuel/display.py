"""Fuel presentation in mass, volume, and estimated endurance.

Mass is the canonical calculation quantity.

Volume requires an explicit fuel density.
Endurance requires an explicit fuel-consumption rate.

These conversions do not establish operational fuel adequacy.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FuelDisplayBasis:
    """Assumptions required for fuel display conversions."""

    density_kg_per_litre: float | None = None
    consumption_kg_per_hour: float | None = None

    def __post_init__(self):
        """Validate fuel conversion assumptions."""

        for name, value in (
            ("Fuel density", self.density_kg_per_litre),
            ("Fuel consumption", self.consumption_kg_per_hour),
        ):
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive.")


@dataclass(frozen=True)
class FuelDisplay:
    """Fuel quantity expressed in three complementary units."""

    kilograms: float
    litres: float | None
    minutes: float | None

    @property
    def formatted(self) -> str:
        """Return all three units in a single display string."""

        litres = f"{self.litres:.1f} L" if self.litres is not None else "N/A L"

        minutes = f"{self.minutes:.0f} min" if self.minutes is not None else "N/A min"

        return f"{self.kilograms:.1f} kg / {litres} / {minutes}"


def display_fuel(
    kilograms: float,
    basis: FuelDisplayBasis,
) -> FuelDisplay:
    """Calculate display values without changing canonical fuel mass."""

    if not isfinite(kilograms) or kilograms < 0:
        raise ValueError("Fuel mass must be finite and non-negative.")

    litres = None
    minutes = None

    if basis.density_kg_per_litre is not None:
        litres = kilograms / basis.density_kg_per_litre

    if basis.consumption_kg_per_hour is not None:
        minutes = (kilograms / basis.consumption_kg_per_hour) * 60.0

    if litres is not None and not isfinite(litres):
        raise ValueError("Converted fuel volume is not finite.")

    if minutes is not None and not isfinite(minutes):
        raise ValueError("Converted fuel endurance is not finite.")

    return FuelDisplay(
        kilograms=kilograms,
        litres=litres,
        minutes=minutes,
    )
