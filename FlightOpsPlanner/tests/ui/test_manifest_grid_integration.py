"""Tests for the integrated passenger and baggage grid."""

import pytest

from app.manifest_grid import build_manifest_rows
from app.manifest_grid_service import (
    ManifestGridError,
    apply_grid_edits,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def sample_records():
    passengers = {
        "P001": Passenger(
            passenger_id="P001",
            name="John Smith",
            verified_weight=85,
        ),
        "P002": Passenger(
            passenger_id="P002",
            name="Sarah",
            verified_weight=65,
        ),
    }

    baggage = {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        ),
        "B002": BaggageItem(
            baggage_id="B002",
            description="Backpack",
            owner_passenger_id="P001",
            verified_weight=7,
        ),
        "B003": BaggageItem(
            baggage_id="B003",
            description="Cargo case",
            verified_weight=25,
        ),
    }

    return passengers, baggage


def test_passenger_baggage_rows_are_grouped():
    passengers, baggage = sample_records()

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    assert list(rows["Type"]) == [
        "Passenger",
        "Bag",
        "Bag",
        "Passenger",
        "Cargo",
    ]


def test_baggage_owner_is_hidden_but_preserved():
    passengers, baggage = sample_records()

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    suitcase = rows.loc[rows["ID"] == "B001"].iloc[0]

    assert suitcase["Owner ID"] == "P001"


def test_passenger_weight_edit_preserves_id():
    passengers, baggage = sample_records()

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    rows.loc[
        rows["ID"] == "P001",
        "Weight (kg)",
    ] = 92

    result = apply_grid_edits(
        rows,
        passengers,
        baggage,
    )

    assert result.passengers["P001"].effective_weight_kg == 92
    assert result.baggage["B001"].owner_passenger_id == "P001"


def test_cargo_remains_unaccompanied():
    passengers, baggage = sample_records()

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    result = apply_grid_edits(
        rows,
        passengers,
        baggage,
    )

    assert result.baggage["B003"].owner_passenger_id is None


def test_invalid_weight_rejected():
    passengers, baggage = sample_records()

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    rows.loc[
        rows["ID"] == "P001",
        "Weight (kg)",
    ] = -10

    with pytest.raises(ManifestGridError):
        apply_grid_edits(
            rows,
            passengers,
            baggage,
        )
