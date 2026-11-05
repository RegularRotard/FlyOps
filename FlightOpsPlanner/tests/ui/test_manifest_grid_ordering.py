"""Tests for passenger-centred manifest grid ordering."""

import pandas as pd

from app.manifest_grid_grouping import group_manifest_rows


def row(record_id, record_type, owner_id=""):
    return {
        "ID": record_id,
        "Type": record_type,
        "Description": record_id,
        "Weight (kg)": 10.0,
        "Owner ID": owner_id,
    }


def test_saved_baggage_follows_owner():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
            row("B001", "Bag", "P001"),
            row("P002", "Passenger"),
            row("B002", "Bag", "P002"),
        ]
    )

    result = group_manifest_rows(saved, [])

    assert list(result["ID"]) == [
        "P001",
        "B001",
        "P002",
        "B002",
    ]


def test_new_baggage_follows_existing_baggage():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
            row("B001", "Bag", "P001"),
            row("P002", "Passenger"),
        ]
    )

    drafts = [
        row("B002", "Bag", "P001"),
        row("B003", "Bag", "P001"),
    ]

    result = group_manifest_rows(saved, drafts)

    assert list(result["ID"]) == [
        "P001",
        "B001",
        "B002",
        "B003",
        "P002",
    ]


def test_new_baggage_follows_correct_owner():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
            row("P002", "Passenger"),
        ]
    )

    drafts = [
        row("B002", "Bag", "P002"),
        row("B001", "Bag", "P001"),
    ]

    result = group_manifest_rows(saved, drafts)

    assert list(result["ID"]) == [
        "P001",
        "B001",
        "P002",
        "B002",
    ]


def test_cargo_stays_at_bottom():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
            row("C001", "Cargo"),
            row("B001", "Bag", "P001"),
        ]
    )

    drafts = [
        row("C002", "Cargo"),
    ]

    result = group_manifest_rows(saved, drafts)

    assert list(result["ID"]) == [
        "P001",
        "B001",
        "C001",
        "C002",
    ]


def test_new_passenger_can_have_draft_baggage():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
        ]
    )

    drafts = [
        row("P002", "Passenger"),
        row("B002", "Bag", "P002"),
    ]

    result = group_manifest_rows(saved, drafts)

    assert list(result["ID"]) == [
        "P001",
        "P002",
        "B002",
    ]


def test_orphaned_baggage_remains_visible():
    saved = pd.DataFrame(
        [
            row("P001", "Passenger"),
            row("B999", "Bag", "MISSING"),
        ]
    )

    result = group_manifest_rows(saved, [])

    assert list(result["ID"]) == [
        "P001",
        "B999",
    ]
