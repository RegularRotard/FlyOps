"""Generic aircraft weight and balance calculations."""

from collections.abc import Iterable

from flightops.weight_balance.models import (
    LoadItem,
    WeightBalanceResult,
)


class WeightBalanceError(Exception):
    """Raised when a weight and balance calculation is invalid."""


def calculate_weight_balance(
    loads: Iterable[LoadItem],
) -> WeightBalanceResult:
    """Calculate total aircraft weight, moment and CG."""

    items = tuple(loads)

    if not items:
        raise WeightBalanceError(
            "At least one load item is required."
        )

    total_weight = sum(
        item.weight_kg for item in items
    )

    if total_weight <= 0:
        raise WeightBalanceError(
            "Total aircraft weight must be greater than zero."
        )

    total_moment = sum(
        item.moment_kg_mm for item in items
    )

    cg = total_moment / total_weight

    return WeightBalanceResult(
        total_weight_kg=total_weight,
        total_moment_kg_mm=total_moment,
        cg_mm=cg,
        items=items,
    )
