"""Evaluate longitudinal CG against configured aircraft envelopes.

Development calculations only. Operational use requires verified
aircraft-specific limitations from applicable approved documentation.
"""

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from math import isfinite

from flightops.aircraft.schemas.configuration import LongitudinalCGEnvelope


class CGEvaluationStatus(StrEnum):
    WITHIN_LIMITS = "within_limits"
    FORWARD_LIMIT_EXCEEDED = "forward_limit_exceeded"
    AFT_LIMIT_EXCEEDED = "aft_limit_exceeded"
    WEIGHT_OUTSIDE_ENVELOPE = "weight_outside_envelope"
    CONFIGURATION_MISSING = "configuration_missing"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class CGEvaluationResult:
    status: CGEvaluationStatus
    weight_kg: float
    cg_mm: float
    forward_limit_mm: float | None = None
    aft_limit_mm: float | None = None
    forward_margin_mm: float | None = None
    aft_margin_mm: float | None = None

    @property
    def within_limits(self) -> bool:
        return self.status == CGEvaluationStatus.WITHIN_LIMITS


def evaluate_longitudinal_cg(
    weight_kg: float,
    cg_mm: float,
    envelope: LongitudinalCGEnvelope | None,
) -> CGEvaluationResult:
    """Evaluate CG using piecewise-linear envelope boundaries."""

    if not isfinite(weight_kg) or not isfinite(cg_mm) or weight_kg <= 0:
        return CGEvaluationResult(
            status=CGEvaluationStatus.INVALID_INPUT,
            weight_kg=weight_kg,
            cg_mm=cg_mm,
        )

    if envelope is None:
        return CGEvaluationResult(
            status=CGEvaluationStatus.CONFIGURATION_MISSING,
            weight_kg=weight_kg,
            cg_mm=cg_mm,
        )

    points = envelope.points

    if weight_kg < points[0].weight_kg or weight_kg > points[-1].weight_kg:
        return CGEvaluationResult(
            status=CGEvaluationStatus.WEIGHT_OUTSIDE_ENVELOPE,
            weight_kg=weight_kg,
            cg_mm=cg_mm,
        )

    for lower, upper in pairwise(points):
        if lower.weight_kg <= weight_kg <= upper.weight_kg:
            fraction = (weight_kg - lower.weight_kg) / (
                upper.weight_kg - lower.weight_kg
            )

            forward_limit = lower.forward_limit_mm + fraction * (
                upper.forward_limit_mm - lower.forward_limit_mm
            )

            aft_limit = lower.aft_limit_mm + fraction * (
                upper.aft_limit_mm - lower.aft_limit_mm
            )

            forward_margin = cg_mm - forward_limit
            aft_margin = aft_limit - cg_mm

            if not all(
                isfinite(value)
                for value in (
                    forward_limit,
                    aft_limit,
                    forward_margin,
                    aft_margin,
                )
            ):
                return CGEvaluationResult(
                    status=CGEvaluationStatus.INVALID_INPUT,
                    weight_kg=weight_kg,
                    cg_mm=cg_mm,
                )

            if cg_mm < forward_limit:
                status = CGEvaluationStatus.FORWARD_LIMIT_EXCEEDED
            elif cg_mm > aft_limit:
                status = CGEvaluationStatus.AFT_LIMIT_EXCEEDED
            else:
                status = CGEvaluationStatus.WITHIN_LIMITS

            return CGEvaluationResult(
                status=status,
                weight_kg=weight_kg,
                cg_mm=cg_mm,
                forward_limit_mm=forward_limit,
                aft_limit_mm=aft_limit,
                forward_margin_mm=forward_margin,
                aft_margin_mm=aft_margin,
            )

    return CGEvaluationResult(
        status=CGEvaluationStatus.INVALID_INPUT,
        weight_kg=weight_kg,
        cg_mm=cg_mm,
    )
