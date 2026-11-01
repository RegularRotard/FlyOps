"""Aircraft weight and balance calculation models."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class LoadItem:
    """A load positioned at a specific aircraft station."""

    name: str
    weight_kg: float
    arm_mm: float

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Load name cannot be empty.")

        if not isfinite(self.weight_kg):
            raise ValueError("Load weight must be finite.")

        if self.weight_kg < 0:
            raise ValueError("Load weight cannot be negative.")

        if not isfinite(self.arm_mm):
            raise ValueError("Load arm must be finite.")

        if not isfinite(self.weight_kg * self.arm_mm):
            raise ValueError("Load moment must be finite.")

    @property
    def moment_kg_mm(self) -> float:
        return self.weight_kg * self.arm_mm


@dataclass(frozen=True)
class WeightBalanceResult:
    """Calculated aircraft loading condition."""

    total_weight_kg: float
    total_moment_kg_mm: float
    cg_mm: float
    items: tuple[LoadItem, ...]
