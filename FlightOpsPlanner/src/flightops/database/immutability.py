"""SQLite triggers protecting historical aircraft revisions."""

IMMUTABLE_TABLES = (
    "aircraft_profile_revisions",
    "aircraft_revision_changes",
    "aircraft_variant_revisions",
    "aircraft_variant_revision_changes",
)


def install_immutability_triggers(connection):
    """Prevent updates and deletions of saved revision records."""

    for table in IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"""
                CREATE TRIGGER IF NOT EXISTS
                    protect_{table}_{operation.lower()}
                BEFORE {operation} ON {table}
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Historical aircraft revisions are immutable'
                    );
                END;
                """
            )
