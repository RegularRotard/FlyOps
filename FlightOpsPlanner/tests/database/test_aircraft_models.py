from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from flightops.database.base import Base
from flightops.database.models import (
    AircraftFamily,
    AircraftProfile,
    AircraftVariant,
    Manufacturer,
)


def test_aircraft_hierarchy():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        manufacturer = Manufacturer(name="Robinson")
        family = AircraftFamily(
            manufacturer=manufacturer,
            name="R44",
        )
        raven_i = AircraftVariant(
            family=family,
            designation="Raven I",
        )
        raven_ii = AircraftVariant(
            family=family,
            designation="Raven II",
        )
        aircraft = AircraftProfile(
            variant=raven_ii,
            registration="5H-TEST",
            serial_number="TEST-001",
        )

        session.add(aircraft)
        session.add(raven_i)
        session.commit()

        result = session.scalar(
            select(AircraftProfile).where(
                AircraftProfile.registration == "5H-TEST"
            )
        )

        assert result is not None
        assert result.variant.designation == "Raven II"
        assert result.variant.family.name == "R44"
        assert result.variant.family.manufacturer.name == "Robinson"

        variants = session.scalars(
            select(AircraftVariant)
        ).all()

        assert len(variants) == 2

    engine.dispose()
