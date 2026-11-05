"""Tests for draft manifest undo history."""

from app.manifest_history import (
    ManifestHistory,
    capture_manifest_snapshot,
    snapshot_matches,
)


def sample_snapshot(weight=85):
    return capture_manifest_snapshot(
        passengers={
            "P001": {
                "name": "John",
                "weight": weight,
            }
        },
        baggage={
            "B001": {
                "owner": "P001",
                "weight": 18,
            }
        },
        assignments={
            "LEG001": {
                "passengers": {"P001"},
                "baggage": {"B001"},
            }
        },
        loading_assignments={
            "LEG001": {
                "passengers": {"P001": "FRONT_SEAT"},
                "baggage": {"B001": "BAGGAGE"},
            }
        },
        baggage_overrides={
            "LEG001": {
                "include": set(),
                "exclude": set(),
            }
        },
        drafts={},
    )


def test_history_starts_empty():
    history = ManifestHistory()

    assert history.can_undo is False
    assert history.count == 0


def test_record_enables_undo():
    history = ManifestHistory()

    history.record(
        "Edit passenger weight",
        sample_snapshot(),
    )

    assert history.can_undo is True
    assert history.count == 1
    assert history.next_description == "Edit passenger weight"


def test_undo_restores_previous_weight():
    history = ManifestHistory()

    history.record(
        "Edit passenger weight",
        sample_snapshot(weight=85),
    )

    restored = history.undo()

    assert restored.passengers["P001"]["weight"] == 85
    assert history.can_undo is False


def test_undo_restores_baggage_relationship():
    history = ManifestHistory()

    history.record(
        "Delete passenger",
        sample_snapshot(),
    )

    restored = history.undo()

    assert restored.baggage["B001"]["owner"] == "P001"


def test_undo_restores_flight_leg_assignments():
    history = ManifestHistory()

    history.record(
        "Delete passenger",
        sample_snapshot(),
    )

    restored = history.undo()

    assert restored.assignments["LEG001"]["passengers"] == {"P001"}

    assert restored.assignments["LEG001"]["baggage"] == {"B001"}


def test_undo_restores_loading_stations():
    history = ManifestHistory()

    history.record(
        "Delete passenger",
        sample_snapshot(),
    )

    restored = history.undo()

    assert restored.loading_assignments["LEG001"]["passengers"]["P001"] == "FRONT_SEAT"


def test_snapshot_does_not_share_mutable_references():
    passengers = {
        "P001": {
            "name": "John",
            "weight": 85,
        }
    }

    snapshot = capture_manifest_snapshot(
        passengers=passengers,
        baggage={},
        assignments={},
        loading_assignments={},
        baggage_overrides={},
        drafts={},
    )

    passengers["P001"]["weight"] = 100

    assert snapshot.passengers["P001"]["weight"] == 85


def test_history_is_bounded():
    history = ManifestHistory(max_entries=3)

    for number in range(5):
        history.record(
            f"Change {number}",
            sample_snapshot(weight=number),
        )

    assert history.count == 3

    restored = history.undo()

    assert restored.passengers["P001"]["weight"] == 4


def test_undo_is_lifo():
    history = ManifestHistory()

    history.record("First", sample_snapshot(weight=85))
    history.record("Second", sample_snapshot(weight=90))

    assert history.undo().passengers["P001"]["weight"] == 90
    assert history.undo().passengers["P001"]["weight"] == 85


def test_snapshot_matches_identical_state():
    snapshot = sample_snapshot()

    assert snapshot_matches(
        snapshot,
        passengers=snapshot.passengers,
        baggage=snapshot.baggage,
        assignments=snapshot.assignments,
        loading_assignments=snapshot.loading_assignments,
        baggage_overrides=snapshot.baggage_overrides,
        drafts=snapshot.drafts,
    )


def test_snapshot_detects_changes():
    snapshot = sample_snapshot()

    changed_passengers = {
        "P001": {
            "name": "John",
            "weight": 92,
        }
    }

    assert not snapshot_matches(
        snapshot,
        passengers=changed_passengers,
        baggage=snapshot.baggage,
        assignments=snapshot.assignments,
        loading_assignments=snapshot.loading_assignments,
        baggage_overrides=snapshot.baggage_overrides,
        drafts=snapshot.drafts,
    )


def test_clear_removes_history():
    history = ManifestHistory()

    history.record("Edit", sample_snapshot())

    history.clear()

    assert history.can_undo is False
    assert history.undo() is None
