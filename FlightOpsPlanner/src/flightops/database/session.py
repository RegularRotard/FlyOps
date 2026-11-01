from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flightops.database import models  # noqa: F401
from flightops.database.base import Base

DATABASE_DIRECTORY = Path("data/databases")
DATABASE_PATH = DATABASE_DIRECTORY / "flightops.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def initialise_database() -> None:
    """Create database tables and install revision protection triggers."""
    from flightops.database.immutability import install_immutability_triggers

    DATABASE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        install_immutability_triggers(connection)

def get_session():
    return SessionLocal()
