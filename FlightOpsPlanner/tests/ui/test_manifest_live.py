"""Regression tests for live passenger and baggage management."""

from app.manifest_live import (
    remove_baggage,
    remove_passenger,
    update_passenger,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def sample_state():
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
            verified_weight=20,
        ),
    }

    assignments = {
        "LEG_A": {
            "passengers": {"P001", "P002"},
            "baggage": {"B001", "B002", "B003"},
        },
        "LEG_B": {
            "passengers": {"P001"},
            "baggage": {"B001"},
        },
    }

    loading = {
        "LEG_A": {
            "passengers": {
                "P001": "SEAT_A",
                "P002": "SEAT_B",
            },
            "baggage": {
                "B001": "BAGGAGE",
                "B002": "BAGGAGE",
            },
        }
    }

    return passengers, baggage, assignments, loading


def test_delete_passenger_cascades_everywhere():
    passengers, baggage, assignments, loading = sample_state()

    (
        updated_passengers,
        updated_baggage,
        updated_assignments,
        updated_loading,
    ) = remove_passenger(
        "P001",
        passengers,
        baggage,
        assignments,
        loading,
    )

    assert "P001" not in updated_passengers
    assert "B001" not in updated_baggage

    for leg in updated_assignments.values():
        assert "P001" not in leg["passengers"]
        assert "B001" not in leg["baggage"]

    assert "P001" not in updated_loading["LEG_A"]["passengers"]
    assert "B001" not in updated_loading["LEG_A"]["baggage"]


def test_deleting_passenger_preserves_other_records():
    passengers, baggage, assignments, loading = sample_state()

    updated = remove_passenger(
        "P001",
        passengers,
        baggage,
        assignments,
        loading,
    )

    updated_passengers, updated_baggage = updated[:2]

    assert "P002" in updated_passengers
    assert "B002" in updated_baggage
    assert "B003" in updated_baggage


def test_deleting_baggage_preserves_owner():
    passengers, baggage, assignments, loading = sample_state()

    (
        updated_baggage,
        updated_assignments,
        updated_loading,
    ) = remove_baggage(
        "B001",
        baggage,
        assignments,
        loading,
        passengers,
    )

    assert "B001" not in updated_baggage
    assert "P001" in updated_assignments["LEG_A"]["passengers"]
    assert "B001" not in updated_loading["LEG_A"]["baggage"]


def test_weight_edit_preserves_passenger_id():
    passengers, _, _, _ = sample_state()

    updated = update_passenger(
        passengers["P001"],
        name="John",
        weight_kg=92,
    )

    assert updated.passenger_id == "P001"
    assert updated.effective_weight_kg == 92


def test_rename_preserves_passenger_id():
    passengers, _, _, _ = sample_state()

    updated = update_passenger(
        passengers["P001"],
        name="John Smith",
        weight_kg=85,
    )

    assert updated.passenger_id == "P001"
    assert updated.name == "John Smith"
