"""Synchronise passenger baggage with flight-leg assignments.

Passenger-owned baggage follows its owner by default.

Per-leg manual overrides allow baggage to be excluded or
carried independently of its owner.
"""

from flightops.operations.manifests.models import BaggageItem


def automatic_baggage_ids(
    passenger_ids: set[str],
    baggage: dict[str, BaggageItem],
) -> set[str]:
    """Find baggage belonging to passengers onboard a leg."""

    return {
        baggage_id
        for baggage_id, item in baggage.items()
        if item.owner_passenger_id in passenger_ids
    }


def derive_overrides(
    passenger_ids: set[str],
    selected_baggage_ids: set[str],
    baggage: dict[str, BaggageItem],
) -> dict[str, set[str]]:
    """Record manual differences from automatic baggage assignment."""

    automatic = automatic_baggage_ids(
        passenger_ids,
        baggage,
    )

    return {
        "include": set(selected_baggage_ids) - automatic,
        "exclude": automatic - set(selected_baggage_ids),
    }


def synchronise_baggage(
    passenger_ids: set[str],
    baggage: dict[str, BaggageItem],
    overrides: dict[str, set[str]] | None = None,
) -> set[str]:
    """Calculate baggage onboard while preserving manual overrides."""

    automatic = automatic_baggage_ids(
        passenger_ids,
        baggage,
    )

    if overrides is None:
        return automatic

    valid_ids = set(baggage)

    include = set(overrides.get("include", ())) & valid_ids
    exclude = set(overrides.get("exclude", ())) & valid_ids

    return (automatic | include) - exclude


def reconcile_baggage_overrides(
    overrides: dict[str, dict[str, set[str]]],
    leg_uids: list[str],
    baggage_ids: set[str],
) -> dict[str, dict[str, set[str]]]:
    """Remove overrides for deleted legs and baggage records."""

    result = {}

    for uid in leg_uids:
        previous = overrides.get(uid, {})

        result[uid] = {
            "include": (set(previous.get("include", ())) & baggage_ids),
            "exclude": (set(previous.get("exclude", ())) & baggage_ids),
        }

    return result
