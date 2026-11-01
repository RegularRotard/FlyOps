"""Validated aircraft configuration management."""

from copy import deepcopy
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import (
    AircraftRevisionService,
)
from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    ConfigurationStatus,
)
from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
)


class AircraftConfigurationError(Exception):
    """Raised when an aircraft configuration operation fails."""


class AircraftConfigurationService:
    """Validate aircraft configurations before creating revisions."""

    def __init__(self, session: Session):
        self.session = session
        self.revisions = AircraftRevisionService(session)

    def save_configuration(
        self,
        profile: AircraftProfile,
        configuration: dict[str, Any],
        description: str,
        changed_by: str | None = None,
    ) -> AircraftProfileRevision:
        """Validate and save a new aircraft configuration revision."""

        try:
            validated = AircraftConfiguration.model_validate(
                configuration
            )
        except ValidationError as exc:
            raise AircraftConfigurationError(
                f"Invalid aircraft configuration: {exc}"
            ) from exc

        if validated.status == ConfigurationStatus.OPERATIONALLY_VERIFIED:
            raise AircraftConfigurationError(
                "Operational verification cannot be assigned "
                "through configuration editing."
            )

        if validated.registration != profile.registration:
            raise AircraftConfigurationError(
                "Configuration registration does not match "
                "the aircraft profile."
            )

        if validated.serial_number != profile.serial_number:
            raise AircraftConfigurationError(
                "Configuration serial number does not match "
                "the aircraft profile."
            )

        if validated.variant_id != profile.variant_id:
            raise AircraftConfigurationError(
                "Configuration variant does not match "
                "the aircraft profile."
            )

        snapshot = validated.model_dump(mode="json")

        return self.revisions.create_revision(
            profile=profile,
            configuration=deepcopy(snapshot),
            description=description,
            changed_by=changed_by,
        )

    def get_current_configuration(
        self,
        profile: AircraftProfile,
    ) -> AircraftConfiguration | None:
        """Return the aircraft's latest validated configuration."""

        if profile.current_revision_id is None:
            return None

        revision = self.session.get(
            AircraftProfileRevision,
            profile.current_revision_id,
        )

        if revision is None:
            raise AircraftConfigurationError(
                "Aircraft current revision could not be found."
            )

        return AircraftConfiguration.model_validate(
            revision.snapshot
        )
