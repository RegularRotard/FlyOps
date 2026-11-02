"""Revision management for individual aircraft configurations."""

from copy import deepcopy
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from flightops.database.base import utc_now
from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
    AircraftRevisionChange,
)

_UNSPECIFIED = object()


class AircraftRevisionError(Exception):
    """Raised when an aircraft revision operation is invalid."""


class AircraftRevisionService:
    """Create, compare, retrieve and restore aircraft profile revisions."""

    def __init__(self, session: Session):
        self.session = session

    def create_revision(
        self,
        profile: AircraftProfile,
        configuration: dict[str, Any],
        description: str,
        changed_by: str | None = None,
        expected_revision_id: str | None | object = _UNSPECIFIED,
    ) -> AircraftProfileRevision:
        """Create a new revision without modifying historical snapshots."""

        if not description.strip():
            raise AircraftRevisionError("A revision description is required.")

        if not isinstance(configuration, dict):
            raise AircraftRevisionError("Aircraft configuration must be a dictionary.")

        # Flush pending aircraft records before creating revision links.
        self.session.add(profile)
        self.session.flush()

        # Retrieve the latest existing revision.
        latest = self.session.scalar(
            select(AircraftProfileRevision)
            .where(AircraftProfileRevision.profile_id == profile.id)
            .order_by(AircraftProfileRevision.revision_number.desc())
            .limit(1)
        )

        current_id = latest.id if latest else None

        if (
            expected_revision_id is not _UNSPECIFIED
            and current_id != expected_revision_id
        ):
            raise AircraftRevisionError(
                "Aircraft configuration has changed since it was loaded. "
                "Reload the latest revision before saving."
            )

        previous_snapshot = deepcopy(latest.snapshot) if latest else {}

        new_snapshot = deepcopy(configuration)

        if latest and previous_snapshot == new_snapshot:
            raise AircraftRevisionError("Configuration has not changed.")

        revision_number = latest.revision_number + 1 if latest else 1

        revision = AircraftProfileRevision(
            profile_id=profile.id,
            revision_number=revision_number,
            parent_revision_id=latest.id if latest else None,
            snapshot=new_snapshot,
            change_description=description,
            changed_by=changed_by,
            created_at=utc_now(),
        )

        self.session.add(revision)
        self.session.flush()

        changes = self.compare_snapshots(
            previous_snapshot,
            new_snapshot,
        )

        for change in changes:
            self.session.add(
                AircraftRevisionChange(
                    revision_id=revision.id,
                    field_path=change["field_path"],
                    old_value=change["old_value"],
                    new_value=change["new_value"],
                )
            )

        # Atomically update the current revision pointer.
        #
        # The database will only accept the update if the aircraft
        # still references the revision we originally loaded.

        statement = (
            update(AircraftProfile)
            .where(AircraftProfile.id == profile.id)
            .where(
                AircraftProfile.current_revision_id.is_(None)
                if current_id is None
                else AircraftProfile.current_revision_id == current_id
            )
            .values(current_revision_id=revision.id)
        )

        result = self.session.execute(statement)

        if result.rowcount != 1:
            raise AircraftRevisionError(
                "Aircraft configuration has changed since it was loaded. "
                "Reload the latest revision before saving."
            )

        # Keep the ORM object consistent with the database.
        self.session.expire(profile, ["current_revision_id"])

        self.session.flush()

        return revision

    def get_history(
        self,
        profile_id: str,
    ) -> list[AircraftProfileRevision]:
        """Return revisions in chronological order."""

        return list(
            self.session.scalars(
                select(AircraftProfileRevision)
                .where(AircraftProfileRevision.profile_id == profile_id)
                .order_by(AircraftProfileRevision.revision_number)
            )
        )

    def get_revision(
        self,
        profile_id: str,
        revision_number: int,
    ) -> AircraftProfileRevision:
        """Retrieve a specific revision."""

        revision = self.session.scalar(
            select(AircraftProfileRevision).where(
                AircraftProfileRevision.profile_id == profile_id,
                AircraftProfileRevision.revision_number == revision_number,
            )
        )

        if revision is None:
            raise AircraftRevisionError(f"Revision {revision_number} not found.")

        return revision

    def restore_revision(
        self,
        profile: AircraftProfile,
        revision_number: int,
        changed_by: str | None = None,
    ) -> AircraftProfileRevision:
        """Restore an earlier snapshot by creating a new revision."""

        old_revision = self.get_revision(
            profile.id,
            revision_number,
        )

        return self.create_revision(
            profile=profile,
            configuration=deepcopy(old_revision.snapshot),
            description=f"Restored configuration from revision {revision_number}",
            changed_by=changed_by,
        )

    @staticmethod
    def compare_snapshots(
        old: dict[str, Any],
        new: dict[str, Any],
        prefix: str = "",
    ) -> list[dict[str, Any]]:
        """Compare nested dictionaries and return changed fields."""

        changes = []

        keys = sorted(set(old) | set(new))

        for key in keys:
            field_path = f"{prefix}.{key}" if prefix else key

            old_exists = key in old
            new_exists = key in new

            old_value = old.get(key)
            new_value = new.get(key)

            if isinstance(old_value, dict) and isinstance(new_value, dict):
                changes.extend(
                    AircraftRevisionService.compare_snapshots(
                        old_value,
                        new_value,
                        field_path,
                    )
                )

            elif old_exists != new_exists or old_value != new_value:
                changes.append(
                    {
                        "field_path": field_path,
                        "old_value": deepcopy(old_value),
                        "new_value": deepcopy(new_value),
                    }
                )

        return changes
