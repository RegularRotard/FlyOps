"""Tests for passenger and baggage flight-leg assignments."""

import pytest

from app.manifest_assignments import (
    assign_journey,
    build_leg_manifests,
    find_discontinuous_assignments,
    reconcile_assignments,
)

LEGS = ["UID_A", "UID_B", "UID_C"]


def empty_assignments():
    return reconcile_assignments(
        {},
        LEGS,
        ["P001", "P002"],
        ["B001"],
    )


def test_initialise_empty_assignments():
    assignments = empty_assignments()

    assert list(assignments) == LEGS
    assert assignments["UID_A"]["passengers"] == set()


def test_passenger_boards_first_and_leaves_second():
    assignments = empty_assignments()

    assign_journey(
        assignments,
        LEGS,
        record_id="P001",
        record_type="passengers",
        board_uid="UID_A",
        disembark_after_uid="UID_B",
    )

    assert "P001" in assignments["UID_A"]["passengers"]
    assert "P001" in assignments["UID_B"]["passengers"]
    assert "P001" not in assignments["UID_C"]["passengers"]


def test_passenger_boards_on_second_leg():
    assignments = empty_assignments()

    assign_journey(
        assignments,
        LEGS,
        record_id="P002",
        record_type="passengers",
        board_uid="UID_B",
        disembark_after_uid="UID_B",
    )

    assert "P002" not in assignments["UID_A"]["passengers"]
    assert "P002" in assignments["UID_B"]["passengers"]


def test_baggage_can_travel_separately():
    assignments = empty_assignments()

    assign_journey(
        assignments,
        LEGS,
        record_id="B001",
        record_type="baggage",
        board_uid="UID_A",
        disembark_after_uid="UID_C",
    )

    assert all("B001" in assignments[uid]["baggage"] for uid in LEGS)


def test_invalid_disembarkation_order_rejected():
    assignments = empty_assignments()

    with pytest.raises(ValueError):
        assign_journey(
            assignments,
            LEGS,
            record_id="P001",
            record_type="passengers",
            board_uid="UID_C",
            disembark_after_uid="UID_A",
        )


def test_assignments_follow_stable_uid_after_reorder():
    assignments = empty_assignments()

    assignments["UID_A"]["passengers"].add("P001")

    reordered = ["UID_C", "UID_B", "UID_A"]

    updated = reconcile_assignments(
        assignments,
        reordered,
        ["P001", "P002"],
        ["B001"],
    )

    assert "P001" in updated["UID_A"]["passengers"]
    assert "P001" not in updated["UID_C"]["passengers"]


def test_deleted_leg_removed():
    assignments = empty_assignments()

    updated = reconcile_assignments(
        assignments,
        ["UID_A", "UID_C"],
        ["P001"],
        ["B001"],
    )

    assert "UID_B" not in updated


def test_deleted_passenger_reference_removed():
    assignments = empty_assignments()

    assignments["UID_A"]["passengers"].add("P001")

    updated = reconcile_assignments(
        assignments,
        LEGS,
        ["P002"],
        ["B001"],
    )

    assert "P001" not in updated["UID_A"]["passengers"]


def test_build_manifest_preserves_assignment():
    assignments = empty_assignments()

    assignments["UID_A"]["passengers"].add("P001")

    manifests = build_leg_manifests(
        assignments,
        LEGS,
    )

    assert manifests[0].leg_uid == "UID_A"
    assert "P001" in manifests[0].passenger_ids


def test_discontinuous_journey_detected():
    assignments = empty_assignments()

    assignments["UID_A"]["passengers"].add("P001")
    assignments["UID_C"]["passengers"].add("P001")

    result = find_discontinuous_assignments(
        assignments,
        LEGS,
        "passengers",
    )

    assert result == {"P001"}


def test_continuous_journey_accepted():
    assignments = empty_assignments()

    assignments["UID_A"]["passengers"].add("P001")
    assignments["UID_B"]["passengers"].add("P001")

    result = find_discontinuous_assignments(
        assignments,
        LEGS,
        "passengers",
    )

    assert result == set()
