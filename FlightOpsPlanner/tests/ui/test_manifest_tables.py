"""Tests for compact passenger and baggage register editing."""

import pandas as pd
import pytest

from app.manifest_tables import (
    apply_baggage_rows,
    apply_passenger_rows,
    baggage_rows,
    owner_options,
    passenger_rows,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)
from flightops.operations.manifests.service import (
    calculate_leg_load,
)


def passengers():
    return {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
            verified_weight=85,
        ),
        "P002": Passenger(
            passenger_id="P002",
            name="Sarah",
            verified_weight=65,
        ),
    }


def test_passenger_table_has_single_weight_column():
    table = passenger_rows(passengers())

    assert list(table.columns) == [
        "ID",
        "Name",
        "Weight (kg)",
    ]


def test_edit_weight_preserves_passenger_id():
    existing = passengers()

    table = passenger_rows(existing)

    table.loc[
        table["ID"] == "P001",
        "Weight (kg)",
    ] = 92

    updated = apply_passenger_rows(table, existing)

    assert "P001" in updated
    assert updated["P001"].effective_weight_kg == 92


def test_new_passenger_receives_unique_id():
    existing = passengers()

    table = passenger_rows(existing)

    table.loc[len(table)] = {
        "ID": None,
        "Name": "David",
        "Weight (kg)": 90,
    }

    updated = apply_passenger_rows(table, existing)

    assert len(updated) == 3

    new_ids = set(updated) - set(existing)

    assert len(new_ids) == 1


def test_deleted_passenger_removed():
    existing = passengers()

    table = passenger_rows(existing)

    table = table[table["ID"] != "P001"].copy()

    updated = apply_passenger_rows(table, existing)

    assert "P001" not in updated
    assert "P002" in updated


def test_negative_weight_rejected():
    existing = passengers()

    table = passenger_rows(existing)

    table.loc[
        table["ID"] == "P001",
        "Weight (kg)",
    ] = -5

    with pytest.raises(ValueError):
        apply_passenger_rows(table, existing)


def test_baggage_table_has_single_weight_column():
    existing = {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        )
    }

    table = baggage_rows(existing, passengers())

    assert list(table.columns) == [
        "ID",
        "Description",
        "Owner",
        "Weight (kg)",
    ]


def test_baggage_owner_preserved():
    existing_passengers = passengers()

    existing_baggage = {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        )
    }

    labels = owner_options(existing_passengers)

    table = baggage_rows(
        existing_baggage,
        existing_passengers,
    )

    updated = apply_baggage_rows(
        table,
        existing_baggage,
        existing_passengers,
        labels,
    )

    assert updated["B001"].owner_passenger_id == "P001"


def test_duplicate_names_have_distinct_owner_labels():
    existing = {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
            verified_weight=85,
        ),
        "P002": Passenger(
            passenger_id="P002",
            name="John",
            verified_weight=90,
        ),
    }

    labels = owner_options(existing)

    assert len(labels) == 3
    assert set(labels.values()) == {
        "",
        "P001",
        "P002",
    }


def test_weight_update_changes_all_matching_leg_loads():
    existing = passengers()

    table = passenger_rows(existing)

    table.loc[
        table["ID"] == "P001",
        "Weight (kg)",
    ] = 92

    updated = apply_passenger_rows(table, existing)

    first = LegManifest(
        leg_uid="UID_A",
        passenger_ids=frozenset({"P001"}),
    )

    second = LegManifest(
        leg_uid="UID_B",
        passenger_ids=frozenset({"P001", "P002"}),
    )

    first_load = calculate_leg_load(
        first,
        updated,
        {},
    )

    second_load = calculate_leg_load(
        second,
        updated,
        {},
    )

    assert first_load.total_weight_kg == 92
    assert second_load.total_weight_kg == 157


def test_blank_new_row_is_ignored():
    existing = passengers()

    table = passenger_rows(existing)

    blank = pd.DataFrame(
        [
            {
                "ID": None,
                "Name": "",
                "Weight (kg)": None,
            }
        ]
    )

    table = pd.concat(
        [table, blank],
        ignore_index=True,
    )

    updated = apply_passenger_rows(table, existing)

    assert len(updated) == 2
