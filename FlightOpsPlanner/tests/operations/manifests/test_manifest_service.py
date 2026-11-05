"""Tests for per-leg passenger and baggage load calculations."""

import pytest

from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)
from flightops.operations.manifests.service import (
    calculate_leg_load,
    calculate_operation_loads,
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
        "P003": Passenger(
            passenger_id="P003",
            name="David",
            declared_weight=90,
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
            description="David's suitcase",
            owner_passenger_id="P003",
            declared_weight=20,
        ),
    }

    return passengers, baggage


def test_single_leg_load():
    passengers, baggage = sample_records()

    manifest = LegManifest(
        leg_uid="LEG_UID_001",
        passenger_ids=frozenset({"P001", "P002"}),
        baggage_ids=frozenset({"B001", "B002"}),
    )

    result = calculate_leg_load(
        manifest,
        passengers,
        baggage,
    )

    assert result.passenger_count == 2
    assert result.baggage_count == 2

    assert result.passenger_weight_kg == pytest.approx(150)
    assert result.baggage_weight_kg == pytest.approx(25)
    assert result.total_weight_kg == pytest.approx(175)

    assert result.ready_for_weight_and_balance


def test_different_loads_on_different_legs():
    passengers, baggage = sample_records()

    manifests = [
        LegManifest(
            leg_uid="UID_001",
            passenger_ids=frozenset({"P001", "P002"}),
            baggage_ids=frozenset({"B001", "B002"}),
        ),
        LegManifest(
            leg_uid="UID_002",
            passenger_ids=frozenset({"P002", "P003"}),
            baggage_ids=frozenset({"B002", "B003"}),
        ),
        LegManifest(
            leg_uid="UID_003",
        ),
    ]

    results = calculate_operation_loads(
        manifests,
        passengers,
        baggage,
    )

    assert results["UID_001"].total_weight_kg == pytest.approx(175)

    assert results["UID_002"].total_weight_kg == pytest.approx(182)

    assert results["UID_003"].total_weight_kg == 0

    assert results["UID_002"].unverified_weight_count == 2


def test_empty_flight_leg():
    passengers, baggage = sample_records()

    manifest = LegManifest(leg_uid="UID_EMPTY")

    result = calculate_leg_load(
        manifest,
        passengers,
        baggage,
    )

    assert result.passenger_count == 0
    assert result.baggage_count == 0
    assert result.total_weight_kg == 0


def test_missing_passenger_weight():
    passengers = {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
        )
    }

    manifest = LegManifest(
        leg_uid="UID_001",
        passenger_ids=frozenset({"P001"}),
    )

    result = calculate_leg_load(
        manifest,
        passengers,
        {},
    )

    assert result.missing_weight_count == 1
    assert not result.ready_for_weight_and_balance


def test_missing_passenger_record():
    manifest = LegManifest(
        leg_uid="UID_001",
        passenger_ids=frozenset({"UNKNOWN"}),
    )

    result = calculate_leg_load(
        manifest,
        {},
        {},
    )

    assert result.missing_weight_count == 1
    assert result.warnings


def test_baggage_without_owner_onboard():
    passengers, baggage = sample_records()

    manifest = LegManifest(
        leg_uid="UID_001",
        passenger_ids=frozenset({"P002"}),
        baggage_ids=frozenset({"B001"}),
    )

    result = calculate_leg_load(
        manifest,
        passengers,
        baggage,
    )

    assert any("without assigned owner" in warning for warning in result.warnings)


def test_unverified_weight_flagged():
    passengers, baggage = sample_records()

    manifest = LegManifest(
        leg_uid="UID_001",
        passenger_ids=frozenset({"P003"}),
    )

    result = calculate_leg_load(
        manifest,
        passengers,
        baggage,
    )

    assert result.unverified_weight_count == 1
    assert not result.ready_for_weight_and_balance


def test_duplicate_leg_manifest_rejected():
    manifests = [
        LegManifest(leg_uid="UID_001"),
        LegManifest(leg_uid="UID_001"),
    ]

    with pytest.raises(ValueError):
        calculate_operation_loads(
            manifests,
            {},
            {},
        )
