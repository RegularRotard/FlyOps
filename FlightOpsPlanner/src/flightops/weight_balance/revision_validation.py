"""Revision-bound aircraft weight and balance validation.

Ensures calculations and limitations originate from the same aircraft
configuration revision.

Results are not flight-release authorisations.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    ConfigurationStatus,
)
from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    VersionedWBResult,
    WBLoadAssignment,
    calculate_from_revision,
)
from flightops.weight_balance.validation import (
    WBValidationResult,
    WBValidationStatus,
    WBWeightCheck,
    validate_weight_balance,
)


class WBVerificationLevel(StrEnum):
    DEVELOPMENT = "development"
    VERIFIED = "verified"


@dataclass(frozen=True)
class RevisionBoundWBResult:
    """A loading assessment tied to one configuration revision."""

    calculation: VersionedWBResult
    validation: WBValidationResult
    verification_level: WBVerificationLevel

    @property
    def passed(self) -> bool:
        """True only for passing checks using a verified configuration."""
        return (
            self.verification_level == WBVerificationLevel.VERIFIED
            and self.validation.status == WBValidationStatus.PASS
        )

    @property
    def development_passed(self) -> bool:
        """Indicate whether the configured mathematical checks passed."""
        return self.validation.status == WBValidationStatus.PASS


def validate_from_revision(
    revision: AircraftProfileRevision,
    assignments: tuple[WBLoadAssignment, ...],
    aircraft: AircraftProfile,
    *,
    weight_check: WBWeightCheck = WBWeightCheck.TAKEOFF,
) -> RevisionBoundWBResult:
    """Calculate and validate loading using one immutable revision."""

    if aircraft is None:
        raise ConfigurationAdapterError(
            "An aircraft profile is required for revision-bound validation."
        )

    if not isinstance(weight_check, WBWeightCheck):
        raise TypeError("Invalid weight check type.")

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    calculation = calculate_from_revision(
        revision,
        assignments,
        aircraft=aircraft,
    )

    wb = configuration.weight_balance

    if wb is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    validation = validate_weight_balance(
        calculation,
        wb.weight_limits,
        wb.longitudinal_cg_envelope,
        weight_check=weight_check,
    )

    if configuration.status == ConfigurationStatus.OPERATIONALLY_VERIFIED:
        verification_level = WBVerificationLevel.VERIFIED
    else:
        verification_level = WBVerificationLevel.DEVELOPMENT

    return RevisionBoundWBResult(
        calculation=calculation,
        validation=validation,
        verification_level=verification_level,
    )
