"""Tests for baggage descriptions and passenger grouping."""

from app.manifest_grid import build_manifest_rows
from app.manifest_grid_service import clean_baggage_description
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def test_removes_one_legacy_prefix():
    assert clean_baggage_description("↳ Suitcase") == "Suitcase"


def test_removes_repeated_legacy_prefixes():
    assert clean_baggage_description("↳ ↳ ↳ Suitcase") == "Suitcase"


def test_cleaning_is_idempotent():
    first = clean_baggage_description("↳ ↳ Backpack")

    second = clean_baggage_description(first)

    assert first == second == "Backpack"


def test_saved_baggage_follows_owner():
    passengers = {
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
            owner_passenger_id="P002",
            verified_weight=7,
        ),
    }

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    assert list(rows["ID"]) == [
        "P001",
        "B001",
        "P002",
        "B002",
    ]


def test_display_does_not_add_prefix():
    passengers = {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
            verified_weight=85,
        )
    }

    baggage = {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        )
    }

    rows = build_manifest_rows(
        passengers,
        baggage,
    )

    assert rows.iloc[1]["Description"] == "Suitcase"
