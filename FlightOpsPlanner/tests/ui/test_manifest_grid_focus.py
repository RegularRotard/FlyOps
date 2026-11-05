"""Tests for stable record-based grid focusing."""

import pandas as pd

from app.manifest_grid_focus import find_record_row


def rows():
    return pd.DataFrame(
        [
            {"ID": "P001", "Type": "Passenger"},
            {"ID": "B001", "Type": "Bag"},
            {"ID": "B002", "Type": "Bag"},
            {"ID": "P002", "Type": "Passenger"},
            {"ID": "B003", "Type": "Bag"},
        ]
    )


def test_focus_first_passenger():
    assert (
        find_record_row(
            rows(),
            "P001",
        )
        == 0
    )


def test_focus_baggage_below_owner():
    assert (
        find_record_row(
            rows(),
            "B002",
        )
        == 2
    )


def test_focus_second_passenger():
    assert (
        find_record_row(
            rows(),
            "P002",
        )
        == 3
    )


def test_unknown_record_has_no_focus():
    assert (
        find_record_row(
            rows(),
            "MISSING",
        )
        is None
    )


def test_no_focus_requested():
    assert (
        find_record_row(
            rows(),
            None,
        )
        is None
    )


def test_empty_grid():
    assert (
        find_record_row(
            pd.DataFrame(columns=["ID"]),
            "P001",
        )
        is None
    )


def test_focus_uses_position_not_dataframe_index():
    dataframe = rows()
    dataframe.index = [10, 20, 30, 40, 50]

    assert (
        find_record_row(
            dataframe,
            "B002",
        )
        == 2
    )
