"""Read-only aircraft catalogue for the FlyOps prototype.

Uses the existing SQLAlchemy aircraft models and local SQLite database.

No database tables are created or modified.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_PATH = PROJECT_ROOT / "data" / "databases" / "flightops.db"


@dataclass(frozen=True)
class AircraftCatalogueEntry:
    """Aircraft identity for the interface."""

    aircraft_id: str
    registration: str
    serial_number: str
    variant_id: str


@dataclass(frozen=True)
class AircraftRevisionEntry:
    """Saved configuration revision available for selection."""

    revision_id: str
    aircraft_id: str
    revision_number: int
    configuration_status: str


def _database_engine():
    """Open the existing local SQLite database."""

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Aircraft database not found: {DATABASE_PATH}")

    return create_engine(
        f"sqlite:///{DATABASE_PATH}",
        connect_args={"check_same_thread": False},
    )


def list_aircraft() -> tuple[AircraftCatalogueEntry, ...]:
    """Return aircraft profiles without modifying the database."""

    engine = _database_engine()

    try:
        with Session(engine) as session:
            profiles = session.scalars(
                select(AircraftProfile).order_by(AircraftProfile.registration)
            ).all()

            return tuple(
                AircraftCatalogueEntry(
                    aircraft_id=str(profile.id),
                    registration=str(profile.registration),
                    serial_number=str(profile.serial_number),
                    variant_id=str(profile.variant_id),
                )
                for profile in profiles
            )

    except SQLAlchemyError as exc:
        raise RuntimeError("Unable to read aircraft profiles.") from exc

    finally:
        engine.dispose()


def list_aircraft_revisions(
    aircraft_id: str,
) -> tuple[AircraftRevisionEntry, ...]:
    """Return saved revisions belonging to the selected aircraft."""

    engine = _database_engine()

    try:
        with Session(engine) as session:
            revisions = session.scalars(
                select(AircraftProfileRevision)
                .where(AircraftProfileRevision.profile_id == aircraft_id)
                .order_by(AircraftProfileRevision.revision_number.desc())
            ).all()

            results = []

            for revision in revisions:
                snapshot = revision.snapshot

                status = "Unknown"

                if isinstance(snapshot, dict):
                    status = str(snapshot.get("status", "Unknown"))

                results.append(
                    AircraftRevisionEntry(
                        revision_id=str(revision.id),
                        aircraft_id=str(revision.profile_id),
                        revision_number=revision.revision_number,
                        configuration_status=status,
                    )
                )

            return tuple(results)

    except SQLAlchemyError as exc:
        raise RuntimeError("Unable to read aircraft configuration revisions.") from exc

    finally:
        engine.dispose()
