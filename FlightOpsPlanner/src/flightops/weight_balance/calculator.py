"""Generic aircraft weight and balance calculations."""

from collections.abc import Iterable
from math import fsum, isfinite

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

    try:
        total_weight = fsum(
            item.weight_kg for item in items
        )
    except OverflowError as exc:
        raise WeightBalanceError(
            "Total aircraft weight exceeds numerical limits."
        ) from exc

    if not isfinite(total_weight) or total_weight <= 0:
        raise WeightBalanceError(
            "Total aircraft weight must be positive and finite."
        )

    try:
        total_moment = fsum(
            item.moment_kg_mm for item in items
        )
    except OverflowError as exc:
        raise WeightBalanceError(
            "Total aircraft moment exceeds numerical limits."
        ) from exc

    if not isfinite(total_moment):
        raise WeightBalanceError(
            "Total aircraft moment must be finite."
        )

    cg = total_moment / total_weight

    if not isfinite(cg):
        raise WeightBalanceError(
            "Calculated CG must be finite."
        )

    return WeightBalanceResult(
        total_weight_kg=total_weight,
        total_moment_kg_mm=total_moment,
        cg_mm=cg,
        items=items,
    )
