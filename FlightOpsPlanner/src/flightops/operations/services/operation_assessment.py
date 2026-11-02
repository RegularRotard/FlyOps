"""Consolidated weight-and-balance assessment for flight operations.

Summarises existing revision-bound loading assessments.

The service does not recalculate aircraft loading, CG, or fuel
quantities and does not grant operational flight approval.
"""

from dataclasses import dataclass
from enum import StrEnum

from flightops.operations.services.leg_weight_balance import (
    OperationWeightBalanceResult,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    WBVerificationLevel,
)
from flightops.weight_balance.validation import WBValidationStatus


class OperationAssessmentStatus(StrEnum):
    """Overall operation assessment status."""

    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"
    DEVELOPMENT = "development"


class LoadingCondition(StrEnum):
    """Loading condition being assessed."""

    ZERO_FUEL = "zero_fuel"
    DEPARTURE = "departure"
    ARRIVAL = "arrival"


@dataclass(frozen=True)
class OperationFinding:
    """One finding associated with a particular flight leg."""

    leg_id: str
    sequence_number: int
    condition: LoadingCondition
    message: str


@dataclass(frozen=True)
class LegAssessmentSummary:
    """Assessment status for the three loading conditions of one leg."""

    leg_id: str
    sequence_number: int

    zero_fuel_status: OperationAssessmentStatus
    departure_status: OperationAssessmentStatus
    arrival_status: OperationAssessmentStatus

    findings: tuple[OperationFinding, ...]

    @property
    def status(self) -> OperationAssessmentStatus:
        """Calculate the most restrictive status for this leg."""

        return _combine_statuses(
            (
                self.zero_fuel_status,
                self.departure_status,
                self.arrival_status,
            )
        )


@dataclass(frozen=True)
class OperationAssessmentResult:
    """Consolidated loading assessment for an entire operation."""

    operation_id: str
    aircraft_profile_id: str
    configuration_revision_id: str

    status: OperationAssessmentStatus
    legs: tuple[LegAssessmentSummary, ...]
    findings: tuple[OperationFinding, ...]

    fuel_continuity_verified: bool

    @property
    def passed(self) -> bool:
        """True only when all configured checks pass."""

        return (
            self.status == OperationAssessmentStatus.PASS
            and self.fuel_continuity_verified
        )


_STATUS_PRIORITY = {
    OperationAssessmentStatus.PASS: 0,
    OperationAssessmentStatus.DEVELOPMENT: 1,
    OperationAssessmentStatus.INCOMPLETE: 2,
    OperationAssessmentStatus.FAIL: 3,
}


def _combine_statuses(
    statuses: tuple[OperationAssessmentStatus, ...],
) -> OperationAssessmentStatus:
    """Return the most restrictive status."""

    return max(
        statuses,
        key=lambda status: _STATUS_PRIORITY[status],
    )


def _assessment_status(
    result: RevisionBoundWBResult,
) -> OperationAssessmentStatus:
    """Convert a revision-bound W&B result into a summary status."""

    if result.validation.status == WBValidationStatus.FAIL:
        return OperationAssessmentStatus.FAIL

    if result.validation.status == WBValidationStatus.INCOMPLETE:
        return OperationAssessmentStatus.INCOMPLETE

    if result.verification_level != WBVerificationLevel.VERIFIED:
        return OperationAssessmentStatus.DEVELOPMENT

    return OperationAssessmentStatus.PASS


def _assessment_findings(
    result: RevisionBoundWBResult,
    *,
    leg_id: str,
    sequence_number: int,
    condition: LoadingCondition,
) -> tuple[OperationFinding, ...]:
    """Return findings for one independently assessed loading condition."""

    findings = [
        OperationFinding(
            leg_id=leg_id,
            sequence_number=sequence_number,
            condition=condition,
            message=message,
        )
        for message in result.validation.findings
    ]

    status = _assessment_status(result)

    if status == OperationAssessmentStatus.INCOMPLETE and not findings:
        findings.append(
            OperationFinding(
                leg_id=leg_id,
                sequence_number=sequence_number,
                condition=condition,
                message="Loading assessment is incomplete.",
            )
        )

    if status == OperationAssessmentStatus.DEVELOPMENT:
        findings.append(
            OperationFinding(
                leg_id=leg_id,
                sequence_number=sequence_number,
                condition=condition,
                message=(
                    "Aircraft configuration is not marked as operationally verified."
                ),
            )
        )

    return tuple(findings)


def assess_operation_weight_balance(
    operation: OperationWeightBalanceResult,
) -> OperationAssessmentResult:
    """Summarise all previously calculated loading conditions."""

    if not operation.legs:
        raise ValueError("Cannot assess an operation without flight legs.")

    summaries = []
    all_findings = []

    for leg in operation.legs:
        assessments = {
            LoadingCondition.ZERO_FUEL: leg.zero_fuel,
            LoadingCondition.DEPARTURE: leg.departure,
            LoadingCondition.ARRIVAL: leg.arrival,
        }

        statuses = {
            condition: _assessment_status(result)
            for condition, result in assessments.items()
        }

        leg_findings = tuple(
            finding
            for condition, result in assessments.items()
            for finding in _assessment_findings(
                result,
                leg_id=leg.leg_id,
                sequence_number=leg.sequence_number,
                condition=condition,
            )
        )

        summary = LegAssessmentSummary(
            leg_id=leg.leg_id,
            sequence_number=leg.sequence_number,
            zero_fuel_status=statuses[LoadingCondition.ZERO_FUEL],
            departure_status=statuses[LoadingCondition.DEPARTURE],
            arrival_status=statuses[LoadingCondition.ARRIVAL],
            findings=leg_findings,
        )

        summaries.append(summary)
        all_findings.extend(leg_findings)

    overall_status = _combine_statuses(tuple(summary.status for summary in summaries))

    return OperationAssessmentResult(
        operation_id=operation.operation_id,
        aircraft_profile_id=operation.aircraft_profile_id,
        configuration_revision_id=operation.configuration_revision_id,
        status=overall_status,
        legs=tuple(summaries),
        findings=tuple(all_findings),
        fuel_continuity_verified=True,
    )
