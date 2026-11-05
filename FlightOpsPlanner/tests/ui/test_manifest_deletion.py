"""Regression tests for deleted manifest records."""

from app.manifest_assignments import reconcile_assignments


def test_deleted_passenger_removed_from_all_legs():
    assignments = {
        "UID_A": {
            "passengers": {"P001", "P002"},
            "baggage": {"B001"},
        },
        "UID_B": {
            "passengers": {"P001"},
            "baggage": set(),
        },
        "UID_C": {
            "passengers": {"P001", "P003"},
            "baggage": set(),
        },
    }

    updated = reconcile_assignments(
        assignments,
        ["UID_A", "UID_B", "UID_C"],
        ["P002", "P003"],
        ["B001"],
    )

    assert all("P001" not in leg["passengers"] for leg in updated.values())

    assert updated["UID_A"]["passengers"] == {"P002"}
    assert updated["UID_C"]["passengers"] == {"P003"}


def test_deleted_baggage_removed_from_all_legs():
    assignments = {
        "UID_A": {
            "passengers": {"P001"},
            "baggage": {"B001", "B002"},
        },
        "UID_B": {
            "passengers": {"P001"},
            "baggage": {"B001"},
        },
    }

    updated = reconcile_assignments(
        assignments,
        ["UID_A", "UID_B"],
        ["P001"],
        ["B002"],
    )

    assert all("B001" not in leg["baggage"] for leg in updated.values())

    assert updated["UID_A"]["baggage"] == {"B002"}
    assert updated["UID_B"]["baggage"] == set()


def test_renamed_passenger_keeps_assignments():
    assignments = {
        "UID_A": {
            "passengers": {"P001"},
            "baggage": set(),
        },
    }

    # A rename does not change the passenger's stable ID.
    updated = reconcile_assignments(
        assignments,
        ["UID_A"],
        ["P001"],
        [],
    )

    assert updated["UID_A"]["passengers"] == {"P001"}


def test_deleted_passenger_does_not_delete_baggage():
    assignments = {
        "UID_A": {
            "passengers": {"P001"},
            "baggage": {"B001"},
        },
    }

    updated = reconcile_assignments(
        assignments,
        ["UID_A"],
        [],
        ["B001"],
    )

    assert updated["UID_A"]["passengers"] == set()
    assert updated["UID_A"]["baggage"] == {"B001"}
