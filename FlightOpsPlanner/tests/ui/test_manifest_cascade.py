"""Tests for cascading passenger and baggage deletion."""

from app.manifest_assignments import reconcile_assignments
from app.manifest_tables import (
    apply_manifest_rows,
    baggage_rows,
    owner_options,
    passenger_rows,
)
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
            description="John's suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        ),
        "B002": BaggageItem(
            baggage_id="B002",
            description="Sarah's backpack",
            owner_passenger_id="P002",
            verified_weight=7,
        ),
        "B003": BaggageItem(
            baggage_id="B003",
            description="Unaccompanied cargo",
            verified_weight=12,
        ),
    }

    return passengers, baggage


def test_deleting_passenger_deletes_owned_baggage():
    passengers, baggage = sample_records()

    edited_passengers = passenger_rows(passengers)

    edited_passengers = edited_passengers[edited_passengers["ID"] != "P001"].copy()

    edited_baggage = baggage_rows(baggage, passengers)

    updated_passengers, updated_baggage = apply_manifest_rows(
        edited_passengers,
        edited_baggage,
        passengers,
        baggage,
        owner_options(passengers),
    )

    assert "P001" not in updated_passengers
    assert "B001" not in updated_baggage

    assert "P002" in updated_passengers
    assert "B002" in updated_baggage
    assert "B003" in updated_baggage


def test_deleting_passenger_removes_all_leg_assignments():
    passengers, baggage = sample_records()

    edited_passengers = passenger_rows(passengers)

    edited_passengers = edited_passengers[edited_passengers["ID"] != "P001"].copy()

    updated_passengers, updated_baggage = apply_manifest_rows(
        edited_passengers,
        baggage_rows(baggage, passengers),
        passengers,
        baggage,
        owner_options(passengers),
    )

    assignments = {
        "LEG_A": {
            "passengers": {"P001", "P002"},
            "baggage": {"B001", "B002"},
        },
        "LEG_B": {
            "passengers": {"P001"},
            "baggage": {"B001"},
        },
    }

    updated_assignments = reconcile_assignments(
        assignments,
        ["LEG_A", "LEG_B"],
        updated_passengers,
        updated_baggage,
    )

    for leg in updated_assignments.values():
        assert "P001" not in leg["passengers"]
        assert "B001" not in leg["baggage"]

    assert updated_assignments["LEG_A"]["passengers"] == {"P002"}

    assert updated_assignments["LEG_A"]["baggage"] == {"B002"}


def test_other_passengers_and_baggage_are_preserved():
    passengers, baggage = sample_records()

    edited_passengers = passenger_rows(passengers)

    edited_passengers = edited_passengers[edited_passengers["ID"] != "P001"].copy()

    updated_passengers, updated_baggage = apply_manifest_rows(
        edited_passengers,
        baggage_rows(baggage, passengers),
        passengers,
        baggage,
        owner_options(passengers),
    )

    assert updated_passengers["P002"].name == "Sarah"

    assert updated_baggage["B002"].owner_passenger_id == "P002"
    assert updated_baggage["B003"].owner_passenger_id is None


def test_weight_edit_does_not_delete_baggage():
    passengers, baggage = sample_records()

    edited_passengers = passenger_rows(passengers)

    edited_passengers.loc[
        edited_passengers["ID"] == "P001",
        "Weight (kg)",
    ] = 92

    updated_passengers, updated_baggage = apply_manifest_rows(
        edited_passengers,
        baggage_rows(baggage, passengers),
        passengers,
        baggage,
        owner_options(passengers),
    )

    assert updated_passengers["P001"].effective_weight_kg == 92
    assert "B001" in updated_baggage


def test_deleting_only_baggage_preserves_passenger():
    passengers, baggage = sample_records()

    edited_baggage = baggage_rows(baggage, passengers)

    edited_baggage = edited_baggage[edited_baggage["ID"] != "B001"].copy()

    updated_passengers, updated_baggage = apply_manifest_rows(
        passenger_rows(passengers),
        edited_baggage,
        passengers,
        baggage,
        owner_options(passengers),
    )

    assert "P001" in updated_passengers
    assert "B001" not in updated_baggage
