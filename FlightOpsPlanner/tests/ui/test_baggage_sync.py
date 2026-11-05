"""Tests for automatic passenger baggage assignment."""

from app.baggage_sync import (
    automatic_baggage_ids,
    derive_overrides,
    reconcile_baggage_overrides,
    synchronise_baggage,
)
from flightops.operations.manifests.models import BaggageItem


def sample_baggage():
    return {
        "B001": BaggageItem(
            baggage_id="B001",
            description="John's suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        ),
        "B002": BaggageItem(
            baggage_id="B002",
            description="John's backpack",
            owner_passenger_id="P001",
            verified_weight=7,
        ),
        "B003": BaggageItem(
            baggage_id="B003",
            description="Sarah's suitcase",
            owner_passenger_id="P002",
            verified_weight=12,
        ),
        "B004": BaggageItem(
            baggage_id="B004",
            description="Unaccompanied cargo",
            verified_weight=25,
        ),
    }


def test_passenger_baggage_assigned_automatically():
    result = automatic_baggage_ids(
        {"P001"},
        sample_baggage(),
    )

    assert result == {"B001", "B002"}


def test_multiple_passengers():
    result = automatic_baggage_ids(
        {"P001", "P002"},
        sample_baggage(),
    )

    assert result == {"B001", "B002", "B003"}


def test_unaccompanied_cargo_not_automatically_assigned():
    result = automatic_baggage_ids(
        {"P001"},
        sample_baggage(),
    )

    assert "B004" not in result


def test_manual_baggage_exclusion():
    result = synchronise_baggage(
        {"P001"},
        sample_baggage(),
        {
            "include": set(),
            "exclude": {"B001"},
        },
    )

    assert result == {"B002"}


def test_independent_baggage_routing():
    result = synchronise_baggage(
        set(),
        sample_baggage(),
        {
            "include": {"B003", "B004"},
            "exclude": set(),
        },
    )

    assert result == {"B003", "B004"}


def test_removing_passenger_removes_automatic_baggage():
    result = synchronise_baggage(
        set(),
        sample_baggage(),
    )

    assert result == set()


def test_manual_baggage_selection_creates_override():
    overrides = derive_overrides(
        {"P001"},
        {"B002", "B004"},
        sample_baggage(),
    )

    assert overrides["include"] == {"B004"}
    assert overrides["exclude"] == {"B001"}


def test_deleted_baggage_removed_from_overrides():
    overrides = {
        "LEG_A": {
            "include": {"B001", "B004"},
            "exclude": {"B002"},
        }
    }

    updated = reconcile_baggage_overrides(
        overrides,
        ["LEG_A"],
        {"B004"},
    )

    assert updated["LEG_A"]["include"] == {"B004"}
    assert updated["LEG_A"]["exclude"] == set()


def test_deleted_leg_removes_overrides():
    overrides = {
        "LEG_A": {
            "include": {"B004"},
            "exclude": set(),
        }
    }

    updated = reconcile_baggage_overrides(
        overrides,
        [],
        {"B004"},
    )

    assert updated == {}
