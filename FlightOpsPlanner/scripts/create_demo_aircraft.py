"""Create a fictional aircraft for FlyOps UI development.

NEVER use this configuration for operational flight planning.
"""

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from flightops.aircraft.revision_service import AircraftRevisionService
from flightops.aircraft.schemas.configuration import AircraftConfiguration
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftVariant,
    Manufacturer,
)

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/databases/flightops.db"

REGISTRATION = "DEMO-ONLY-001"
SERIAL = "FICTIONAL-001"


def create_demo_aircraft():
    if not DB.is_file():
        raise RuntimeError(
            f"Database missing: {DB}. "
            "No database was created."
        )

    engine = create_engine(f"sqlite:///{DB}")

    try:
        with Session(engine) as session:
            existing = session.scalar(
                select(AircraftProfile).where(
                    AircraftProfile.registration == REGISTRATION
                )
            )

            if existing is not None:
                print(
                    f"Development aircraft already exists: "
                    f"{REGISTRATION}"
                )
                print("No changes made.")
                return

            # Manufacturer
            manufacturer = session.scalar(
                select(Manufacturer).where(
                    Manufacturer.name == "FlyOps Development"
                )
            )

            if manufacturer is None:
                manufacturer = Manufacturer(
                    name="FlyOps Development"
                )
                session.add(manufacturer)
                session.flush()

            # Family
            family = session.scalar(
                select(AircraftFamily).where(
                    AircraftFamily.manufacturer_id == manufacturer.id,
                    AircraftFamily.name == "Test Helicopter",
                )
            )

            if family is None:
                family = AircraftFamily(
                    manufacturer_id=manufacturer.id,
                    name="Test Helicopter",
                    description=(
                        "Fictional aircraft for software testing."
                    ),
                )
                session.add(family)
                session.flush()

            # Variant
            variant = session.scalar(
                select(AircraftVariant).where(
                    AircraftVariant.family_id == family.id,
                    AircraftVariant.designation == "W&B Integration Test",
                )
            )

            if variant is None:
                variant = AircraftVariant(
                    family_id=family.id,
                    designation="W&B Integration Test",
                    description=(
                        "Not representative of a real aircraft."
                    ),
                )
                session.add(variant)
                session.flush()

            # Aircraft profile
            aircraft = AircraftProfile(
                variant_id=variant.id,
                registration=REGISTRATION,
                serial_number=SERIAL,
                nickname="FlyOps Development Helicopter",
            )

            session.add(aircraft)
            session.flush()

            # Fictional loading configuration.
            # These values are deliberately NOT R44 specifications.
            configuration = AircraftConfiguration.model_validate(
                {
                    "registration": REGISTRATION,
                    "serial_number": SERIAL,
                    "variant_id": variant.id,
                    "status": "structurally_valid",
                    "notes": (
                        "FICTIONAL DEVELOPMENT DATA ONLY. "
                        "Not approved for flight planning."
                    ),
                    "technical_documents": [
                        {
                            "document_id": "DEMO-WB-001",
                            "document_type": "development_test_data",
                            "title": (
                                "Fictional FlyOps W&B Test Data"
                            ),
                        }
                    ],
                    "weight_balance": {
                        "basic_empty_weight_kg": 650.0,
                        "basic_empty_weight_longitudinal_arm_mm": 2500.0,
                        "datum_description": (
                            "Fictional development datum"
                        ),
                        "source_document_id": "DEMO-WB-001",
                        "weight_limits": {
                            "maximum_takeoff_weight_kg": 1100.0,
                            "maximum_landing_weight_kg": 1100.0,
                        },
                        "longitudinal_cg_envelope": {
                            "points": [
                                {
                                    "weight_kg": 600.0,
                                    "forward_limit_mm": 2200.0,
                                    "aft_limit_mm": 2900.0,
                                },
                                {
                                    "weight_kg": 1100.0,
                                    "forward_limit_mm": 2300.0,
                                    "aft_limit_mm": 2800.0,
                                },
                            ]
                        },
                        "loading_stations": [
                            {
                                "station_id": "PILOT",
                                "description": "Pilot seat",
                                "category": "crew",
                                "longitudinal_arm_mm": 2000.0,
                                "maximum_load_kg": 150.0,
                            },
                            {
                                "station_id": "PAX_FRONT",
                                "description": "Front passenger seat",
                                "category": "passenger",
                                "longitudinal_arm_mm": 2000.0,
                                "maximum_load_kg": 150.0,
                            },
                            {
                                "station_id": "PAX_REAR",
                                "description": "Rear passenger position",
                                "category": "passenger",
                                "longitudinal_arm_mm": 3000.0,
                                "maximum_load_kg": 250.0,
                            },
                            {
                                "station_id": "BAGGAGE",
                                "description": "Baggage compartment",
                                "category": "baggage",
                                "longitudinal_arm_mm": 3200.0,
                                "maximum_load_kg": 100.0,
                            },
                            {
                                "station_id": "FUEL_MAIN",
                                "description": "Main fuel tank",
                                "category": "usable_fuel",
                                "longitudinal_arm_mm": 2600.0,
                                "maximum_load_kg": 150.0,
                            },
                        ],
                    },
                }
            )

            revision_service = AircraftRevisionService(session)

            revision = revision_service.create_revision(
                profile=aircraft,
                configuration=configuration.model_dump(mode="json"),
                description="Initial fictional development configuration",
                changed_by="FlyOps Development",
            )

            session.commit()

            print("=" * 55)
            print("DEVELOPMENT AIRCRAFT CREATED")
            print("=" * 55)
            print(f"Registration: {aircraft.registration}")
            print(f"Aircraft ID: {aircraft.id}")
            print(f"Revision: {revision.revision_number}")
            print(f"Revision ID: {revision.id}")
            print("Status: STRUCTURALLY VALID")
            print("Operational verification: NO")
            print("Purpose: SOFTWARE TESTING ONLY")

    finally:
        engine.dispose()


if __name__ == "__main__":
    create_demo_aircraft()
