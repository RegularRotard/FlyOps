"""Aircraft weight and balance calculation models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadItem:
    """A load positioned at a specific aircraft station."""

    name: str
    weight_kg: float
    arm_mm: float

    def __post_init__(self):
        if self.weight_kg < 0:
            raise ValueError(
                f"Load '{self.name}' cannot have negative weight."
            )

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
