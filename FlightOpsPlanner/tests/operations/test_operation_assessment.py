"""Tests for consolidated flight-operation W&B assessments."""

from dataclasses import replace

import pytest

from flightops.operations.services.operation_assessment import (
    LoadingCondition,
    OperationAssessmentStatus,
    assess_operation_weight_balance,
)
from flightops.weight_balance.revision_validation import (
    WBVerificationLevel,
)
from flightops.weight_balance.validation import WBValidationStatus
from tests.operations.test_leg_cg_plots import example_operation


def sample_operation():
    assessment, _, _ = example_operation()
    return assessment


def modify_condition(
    operation,
    *,
    leg_index=0,
    condition="departure",
    status=None,
    verification=None,
    findings=None,
):
    """Create a changed assessment without mutating its original."""

    leg = operation.legs[leg_index]
    original = getattr(leg, condition)

    validation_updates = {}

    if status is not None:
        validation_updates["status"] = status

    if findings is not None:
        validation_updates["findings"] = findings

    changed_validation = replace(
        original.validation,
        **validation_updates,
    )

    changed_assessment = replace(
        original,
        validation=changed_validation,
        verification_level=(
            verification if verification is not None else original.verification_level
        ),
    )

    changed_leg = replace(
        leg,
        **{condition: changed_assessment},
    )

    changed_legs = list(operation.legs)
    changed_legs[leg_index] = changed_leg

    return replace(
        operation,
        legs=tuple(changed_legs),
    )


def test_operation_produces_summary_for_each_leg():
    result = assess_operation_weight_balance(sample_operation())

    assert len(result.legs) == 2
    assert result.legs[0].leg_id == "leg-1"
    assert result.legs[1].leg_id == "leg-2"


def test_operation_preserves_revision_identity():
    operation = sample_operation()

    result = assess_operation_weight_balance(operation)

    assert result.configuration_revision_id == operation.configuration_revision_id


def test_failed_departure_marks_operation_failed():
    operation = modify_condition(
        sample_operation(),
        status=WBValidationStatus.FAIL,
        findings=("Maximum takeoff weight exceeded.",),
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.FAIL

    assert any(
        finding.condition == LoadingCondition.DEPARTURE
        and "Maximum takeoff weight" in finding.message
        for finding in result.findings
    )


def test_failed_arrival_marks_operation_failed():
    operation = modify_condition(
        sample_operation(),
        leg_index=1,
        condition="arrival",
        status=WBValidationStatus.FAIL,
        findings=("Landing CG outside limits.",),
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.FAIL

    assert any(
        finding.leg_id == "leg-2" and finding.condition == LoadingCondition.ARRIVAL
        for finding in result.findings
    )


def test_incomplete_condition_marks_operation_incomplete():
    operation = modify_condition(
        sample_operation(),
        condition="arrival",
        status=WBValidationStatus.INCOMPLETE,
        findings=(),
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.INCOMPLETE

    assert any("incomplete" in finding.message.lower() for finding in result.findings)


def test_development_configuration_not_reported_as_pass():
    operation = modify_condition(
        sample_operation(),
        verification=WBVerificationLevel.DEVELOPMENT,
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.DEVELOPMENT
    assert not result.passed


def test_failure_takes_priority_over_incomplete():
    operation = modify_condition(
        sample_operation(),
        condition="departure",
        status=WBValidationStatus.FAIL,
        findings=("Takeoff limit exceeded.",),
    )

    operation = modify_condition(
        operation,
        condition="arrival",
        status=WBValidationStatus.INCOMPLETE,
        findings=(),
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.FAIL


def test_failure_takes_priority_over_development():
    operation = modify_condition(
        sample_operation(),
        condition="departure",
        status=WBValidationStatus.FAIL,
        findings=("Takeoff limit exceeded.",),
    )

    operation = modify_condition(
        operation,
        condition="arrival",
        verification=WBVerificationLevel.DEVELOPMENT,
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.FAIL


def test_zero_fuel_failure_is_independent():
    operation = modify_condition(
        sample_operation(),
        condition="zero_fuel",
        status=WBValidationStatus.FAIL,
        findings=("Zero-fuel CG outside limits.",),
    )

    result = assess_operation_weight_balance(operation)

    assert result.status == OperationAssessmentStatus.FAIL

    assert any(
        finding.condition == LoadingCondition.ZERO_FUEL for finding in result.findings
    )


def test_finding_identifies_correct_leg():
    operation = modify_condition(
        sample_operation(),
        leg_index=1,
        condition="departure",
        status=WBValidationStatus.FAIL,
        findings=("CG limit exceeded.",),
    )

    result = assess_operation_weight_balance(operation)

    matching = [
        finding
        for finding in result.findings
        if finding.message == "CG limit exceeded."
    ]

    assert len(matching) == 1
    assert matching[0].leg_id == "leg-2"
    assert matching[0].sequence_number == 2


def test_empty_operation_rejected():
    operation = replace(
        sample_operation(),
        legs=(),
    )

    with pytest.raises(ValueError, match="without flight legs"):
        assess_operation_weight_balance(operation)


def test_status_priority():
    from flightops.operations.services.operation_assessment import (
        _combine_statuses,
    )

    result = _combine_statuses(
        (
            OperationAssessmentStatus.PASS,
            OperationAssessmentStatus.DEVELOPMENT,
            OperationAssessmentStatus.INCOMPLETE,
            OperationAssessmentStatus.FAIL,
        )
    )

    assert result == OperationAssessmentStatus.FAIL
