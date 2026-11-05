"""Tests for passenger and baggage data models."""

import pytest

from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)


def test_passenger_declared_weight():
    passenger = Passenger(
        passenger_id="P001",
        name="John",
        declared_weight=85,
    )

    assert passenger.effective_weight_kg == 85
    assert not passenger.weight_verified


def test_verified_weight_takes_priority():
    passenger = Passenger(
        passenger_id="P001",
        name="John",
        declared_weight=80,
        verified_weight=92,
    )

    assert passenger.effective_weight_kg == 92
    assert passenger.weight_verified


def test_pounds_converted_to_kg():
    passenger = Passenger(
        passenger_id="P001",
        name="John",
        declared_weight=220.462262,
        weight_unit="lb",
    )

    assert passenger.effective_weight_kg == pytest.approx(
        100,
        abs=0.001,
    )


def test_missing_weight_is_not_zero():
    passenger = Passenger(
        passenger_id="P001",
        name="John",
    )

    assert passenger.effective_weight_kg is None


def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        Passenger(
            passenger_id="P001",
            name="John",
            declared_weight=-5,
        )


def test_nonfinite_weight_rejected():
    with pytest.raises(ValueError):
        Passenger(
            passenger_id="P001",
            name="John",
            declared_weight=float("nan"),
        )


def test_baggage_owner_is_optional():
    item = BaggageItem(
        baggage_id="B001",
        description="Cargo box",
        verified_weight=12,
    )

    assert item.owner_passenger_id is None
    assert item.effective_weight_kg == 12


def test_baggage_weight_verification():
    item = BaggageItem(
        baggage_id="B001",
        description="Suitcase",
        declared_weight=18,
        verified_weight=21,
    )

    assert item.effective_weight_kg == 21
    assert item.weight_verified


def test_leg_manifest_uses_stable_uid():
    manifest = LegManifest(
        leg_uid="abc123",
        passenger_ids=frozenset({"P001", "P002"}),
    )

    assert manifest.leg_uid == "abc123"
    assert len(manifest.passenger_ids) == 2


def test_duplicate_passenger_ids_are_normalised():
    manifest = LegManifest(
        leg_uid="abc123",
        passenger_ids=["P001", "P001", "P002"],
    )

    assert len(manifest.passenger_ids) == 2
