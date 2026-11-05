"""Manage passenger and baggage assignments using stable flight-leg IDs."""

from collections.abc import Iterable

from flightops.operations.manifests.models import LegManifest


def reconcile_assignments(
    assignments: dict[str, dict[str, set[str]]],
    leg_uids: Iterable[str],
    passenger_ids: Iterable[str],
    baggage_ids: Iterable[str],
) -> dict[str, dict[str, set[str]]]:
    """Remove references to deleted legs or manifest records."""

    valid_passengers = set(passenger_ids)
    valid_baggage = set(baggage_ids)

    result = {}

    for uid in leg_uids:
        previous = assignments.get(uid, {})

        result[uid] = {
            "passengers": (set(previous.get("passengers", ())) & valid_passengers),
            "baggage": (set(previous.get("baggage", ())) & valid_baggage),
        }

    return result


def assign_journey(
    assignments: dict[str, dict[str, set[str]]],
    leg_uids: list[str],
    *,
    record_id: str,
    record_type: str,
    board_uid: str,
    disembark_after_uid: str,
) -> None:
    """Assign a passenger or baggage item to a continuous leg range.

    Assignments are attached to stable UIDs, not displayed leg numbers.
    """

    if record_type not in ("passengers", "baggage"):
        raise ValueError("Invalid manifest record type.")

    if not record_id:
        raise ValueError("A manifest record ID is required.")

    if board_uid not in leg_uids:
        raise ValueError("Unknown boarding leg.")

    if disembark_after_uid not in leg_uids:
        raise ValueError("Unknown disembarkation leg.")

    start = leg_uids.index(board_uid)
    end = leg_uids.index(disembark_after_uid)

    if end < start:
        raise ValueError("Disembarkation cannot precede boarding.")

    # Replace the record's previous journey.
    for assignment in assignments.values():
        assignment[record_type].discard(record_id)

    for uid in leg_uids[start : end + 1]:
        assignments[uid][record_type].add(record_id)


def build_leg_manifests(
    assignments: dict[str, dict[str, set[str]]],
    leg_uids: list[str],
) -> list[LegManifest]:
    """Build calculation-ready manifests in flight order."""

    return [
        LegManifest(
            leg_uid=uid,
            passenger_ids=frozenset(assignments[uid]["passengers"]),
            baggage_ids=frozenset(assignments[uid]["baggage"]),
        )
        for uid in leg_uids
    ]


def find_discontinuous_assignments(
    assignments: dict[str, dict[str, set[str]]],
    leg_uids: list[str],
    record_type: str,
) -> set[str]:
    """Find records assigned to separated, nonconsecutive legs."""

    if record_type not in ("passengers", "baggage"):
        raise ValueError("Invalid manifest record type.")

    positions: dict[str, list[int]] = {}

    for index, uid in enumerate(leg_uids):
        for record_id in assignments[uid][record_type]:
            positions.setdefault(record_id, []).append(index)

    return {
        record_id
        for record_id, indices in positions.items()
        if indices != list(range(indices[0], indices[-1] + 1))
    }
