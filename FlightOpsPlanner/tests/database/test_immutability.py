"""Tests for database-level aircraft revision immutability."""

import pytest
from sqlalchemy import create_engine, text

from flightops.database.base import Base
from flightops.database.immutability import install_immutability_triggers


@pytest.fixture
def protected_engine():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        install_immutability_triggers(connection)

    yield engine

    engine.dispose()


def test_all_immutability_triggers_installed(protected_engine):
    with protected_engine.connect() as connection:
        triggers = connection.execute(
            text("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                AND name LIKE 'protect_%'
            """)
        ).all()

    assert len(triggers) == 8


@pytest.mark.parametrize(
    "table",
    [
        "aircraft_profile_revisions",
        "aircraft_revision_changes",
        "aircraft_variant_revisions",
        "aircraft_variant_revision_changes",
    ],
)
def test_revision_tables_have_update_and_delete_protection(
    protected_engine,
    table,
):
    with protected_engine.connect() as connection:
        triggers = (
            connection.execute(
                text("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                AND tbl_name = :table
            """),
                {"table": table},
            )
            .scalars()
            .all()
        )

    assert f"protect_{table}_update" in triggers
    assert f"protect_{table}_delete" in triggers
