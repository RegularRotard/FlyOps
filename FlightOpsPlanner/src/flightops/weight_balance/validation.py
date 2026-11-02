"""Integrated aircraft weight and longitudinal CG validation.

Development calculations only. A PASS indicates only that the checks
implemented here passed; it is not operational flight approval.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from flightops.aircraft.schemas.configuration import (
    AircraftWeightLimits,
    LongitudinalCGEnvelope,
)
from flightops.weight_balance.configuration_adapter import VersionedWBResult
from flightops.weight_balance.envelope import (
    CGEvaluationResult,
    CGEvaluationStatus,
    evaluate_longitudinal_cg,
)


class WBValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class WBWeightCheck(StrEnum):
    TAKEOFF = "takeoff"
    LANDING = "landing"


@dataclass(frozen=True)
class WBValidationResult:
    aircraft_profile_id: str
    configuration_revision_id: str
    configuration_revision_number: int

    status: WBValidationStatus
    weight_check: WBWeightCheck

    total_weight_kg: float
    cg_mm: float

    applicable_maximum_weight_kg: float | None
    weight_margin_kg: float | None

    cg_evaluation: CGEvaluationResult
    findings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == WBValidationStatus.PASS


def validate_weight_balance(
    result: VersionedWBResult,
    weight_limits: AircraftWeightLimits | None,
    longitudinal_envelope: LongitudinalCGEnvelope | None,
    *,
    weight_check: WBWeightCheck = WBWeightCheck.TAKEOFF,
) -> WBValidationResult:
    """Evaluate calculated loading against supplied weight and CG limits."""

    if not isinstance(weight_check, WBWeightCheck):
        raise TypeError("Invalid weight check type.")

    weight = result.calculation.total_weight_kg
    cg = result.calculation.cg_mm

    failures = []
    incomplete = []

    applicable_maximum = None
    weight_margin = None

    if not isfinite(weight) or weight <= 0 or not isfinite(cg):
        incomplete.append("Calculated weight or CG is invalid.")

    if weight_limits is None:
        incomplete.append("Aircraft weight limits are missing.")
    else:
        if weight_check == WBWeightCheck.TAKEOFF:
            applicable_maximum = weight_limits.maximum_takeoff_weight_kg
        else:
            applicable_maximum = weight_limits.maximum_landing_weight_kg

        if applicable_maximum is None:
            incomplete.append(f"Maximum {weight_check.value} weight is not configured.")
        elif isfinite(weight):
            weight_margin = applicable_maximum - weight

            if not isfinite(weight_margin):
                incomplete.append("Weight margin is numerically invalid.")
                weight_margin = None
            elif weight_margin < 0:
                failures.append(f"Maximum {weight_check.value} weight exceeded.")

        minimum = weight_limits.minimum_operating_weight_kg

        if minimum is not None and isfinite(weight) and weight < minimum:
            failures.append("Minimum operating weight not satisfied.")

    cg_evaluation = evaluate_longitudinal_cg(
        weight,
        cg,
        longitudinal_envelope,
    )

    if cg_evaluation.status in (
        CGEvaluationStatus.FORWARD_LIMIT_EXCEEDED,
        CGEvaluationStatus.AFT_LIMIT_EXCEEDED,
        CGEvaluationStatus.WEIGHT_OUTSIDE_ENVELOPE,
    ):
        failures.append(f"Longitudinal CG check: {cg_evaluation.status.value}.")
    elif cg_evaluation.status != CGEvaluationStatus.WITHIN_LIMITS:
        incomplete.append(f"Longitudinal CG check: {cg_evaluation.status.value}.")

    if failures:
        status = WBValidationStatus.FAIL
    elif incomplete:
        status = WBValidationStatus.INCOMPLETE
    else:
        status = WBValidationStatus.PASS

    return WBValidationResult(
        aircraft_profile_id=result.aircraft_profile_id,
        configuration_revision_id=result.configuration_revision_id,
        configuration_revision_number=result.configuration_revision_number,
        status=status,
        weight_check=weight_check,
        total_weight_kg=weight,
        cg_mm=cg,
        applicable_maximum_weight_kg=applicable_maximum,
        weight_margin_kg=weight_margin,
        cg_evaluation=cg_evaluation,
        findings=tuple(failures + incomplete),
    )
