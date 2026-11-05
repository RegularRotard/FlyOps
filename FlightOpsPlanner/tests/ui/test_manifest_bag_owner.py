"""Tests for automatic baggage owner selection."""

from app.manifest_grid_service import resolve_baggage_owner
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def sample_records():
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
    }

    return passengers, baggage


def test_selected_passenger_becomes_owner():
    passengers, baggage = sample_records()

    assert (
        resolve_baggage_owner(
            "P001",
            passengers,
            baggage,
        )
        == "P001"
    )


def test_selected_baggage_uses_its_owner():
    passengers, baggage = sample_records()

    assert (
        resolve_baggage_owner(
            "B001",
            passengers,
            baggage,
        )
        == "P001"
    )


def test_no_selection_uses_latest_passenger():
    passengers, baggage = sample_records()

    assert (
        resolve_baggage_owner(
            None,
            passengers,
            baggage,
        )
        == "P002"
    )


def test_no_passenger_disables_bag_creation():
    assert (
        resolve_baggage_owner(
            None,
            {},
            {},
        )
        is None
    )
