"""Passenger-centred ordering for the FlyOps manifest grid."""

import pandas as pd

GRID_COLUMNS = [
    "ID",
    "Type",
    "Description",
    "Weight (kg)",
    "Owner ID",
]


def group_manifest_rows(
    saved_rows: pd.DataFrame,
    draft_rows: list[dict],
) -> pd.DataFrame:
    """Group passengers, their baggage and independent cargo.

    Ordering:
      1. Saved passenger
      2. Existing baggage belonging to that passenger
      3. New baggage belonging to that passenger
      4. Next passenger
      5. New passengers
      6. Unaccompanied cargo

    Existing record IDs and ownership relationships are preserved.
    """

    saved = saved_rows.to_dict("records")

    passengers = []
    baggage_by_owner = {}
    cargo = []

    for row in saved:
        record_type = row["Type"]

        if record_type == "Passenger":
            passengers.append(dict(row))

        elif record_type == "Bag":
            owner_id = row.get("Owner ID")

            baggage_by_owner.setdefault(
                owner_id,
                [],
            ).append(dict(row))

        elif record_type == "Cargo":
            cargo.append(dict(row))

    draft_passengers = []
    draft_baggage_by_owner = {}
    draft_cargo = []

    for row in draft_rows:
        record_type = row["Type"]

        if record_type == "Passenger":
            draft_passengers.append(dict(row))

        elif record_type == "Bag":
            owner_id = row.get("Owner ID")

            draft_baggage_by_owner.setdefault(
                owner_id,
                [],
            ).append(dict(row))

        elif record_type == "Cargo":
            draft_cargo.append(dict(row))

    result = []

    for passenger in passengers:
        passenger_id = passenger["ID"]

        result.append(passenger)

        result.extend(baggage_by_owner.pop(passenger_id, []))

        result.extend(draft_baggage_by_owner.pop(passenger_id, []))

    for passenger in draft_passengers:
        passenger_id = passenger["ID"]

        result.append(passenger)

        result.extend(baggage_by_owner.pop(passenger_id, []))

        result.extend(draft_baggage_by_owner.pop(passenger_id, []))

    # Do not silently discard orphaned baggage.
    # Display it separately so the problem remains visible.
    orphaned = [row for items in baggage_by_owner.values() for row in items]

    orphaned.extend(row for items in draft_baggage_by_owner.values() for row in items)

    result.extend(orphaned)

    result.extend(cargo)
    result.extend(draft_cargo)

    return pd.DataFrame(
        result,
        columns=GRID_COLUMNS,
    )
