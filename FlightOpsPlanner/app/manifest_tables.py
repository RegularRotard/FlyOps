"""Spreadsheet-style passenger and baggage register helpers."""

from math import isfinite
from uuid import uuid4

import pandas as pd

from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def _weight(value) -> float | None:
    """Parse an optional nonnegative weight in kilograms."""

    if value is None or pd.isna(value):
        return None

    if isinstance(value, str) and not value.strip():
        return None

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Weight must be a number.") from exc

    if not isfinite(result) or result < 0:
        raise ValueError("Weight must be finite and nonnegative.")

    return result


def passenger_rows(
    passengers: dict[str, Passenger],
) -> pd.DataFrame:
    """Create a compact editable passenger table."""

    rows = [
        {
            "ID": passenger.passenger_id,
            "Name": passenger.name,
            "Weight (kg)": passenger.effective_weight_kg,
        }
        for passenger in passengers.values()
    ]

    return pd.DataFrame(
        rows,
        columns=["ID", "Name", "Weight (kg)"],
    )


def owner_options(
    passengers: dict[str, Passenger],
) -> dict[str, str]:
    """Return unambiguous display labels mapped to passenger IDs."""

    counts = {}

    for passenger in passengers.values():
        counts[passenger.name] = counts.get(passenger.name, 0) + 1

    result = {"Unaccompanied": ""}

    for passenger in passengers.values():
        label = passenger.name

        if counts[passenger.name] > 1:
            label = f"{passenger.name} ({passenger.passenger_id[:8]})"

        result[label] = passenger.passenger_id

    return result


def baggage_rows(
    baggage: dict[str, BaggageItem],
    passengers: dict[str, Passenger],
) -> pd.DataFrame:
    """Create an editable baggage table with readable owners."""

    labels = owner_options(passengers)

    reverse_labels = {passenger_id: label for label, passenger_id in labels.items()}

    rows = [
        {
            "ID": item.baggage_id,
            "Description": item.description,
            "Owner": reverse_labels.get(
                item.owner_passenger_id,
                "Unaccompanied",
            ),
            "Weight (kg)": item.effective_weight_kg,
        }
        for item in baggage.values()
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "ID",
            "Description",
            "Owner",
            "Weight (kg)",
        ],
    )


def apply_passenger_rows(
    edited: pd.DataFrame,
    existing: dict[str, Passenger],
) -> dict[str, Passenger]:
    """Build the updated passenger register atomically."""

    result = {}
    seen_existing = set()

    for _, row in edited.iterrows():
        name = str(row.get("Name") or "").strip()

        raw_id = row.get("ID")
        record_id = str(raw_id) if pd.notna(raw_id) and str(raw_id).strip() else ""

        weight = _weight(row.get("Weight (kg)"))

        if not name:
            if weight is None and not record_id:
                continue

            raise ValueError("Every passenger row needs a name.")

        if record_id:
            if record_id not in existing:
                raise ValueError("Unknown passenger ID in edited table.")

            if record_id in seen_existing:
                raise ValueError("Duplicate passenger record.")

            seen_existing.add(record_id)
        else:
            record_id = uuid4().hex

        previous = existing.get(record_id)

        result[record_id] = Passenger(
            passenger_id=record_id,
            name=name,
            verified_weight=weight,
            weight_unit="kg",
            notes=previous.notes if previous else "",
        )

    return result


def apply_baggage_rows(
    edited: pd.DataFrame,
    existing: dict[str, BaggageItem],
    passengers: dict[str, Passenger],
    owner_labels: dict[str, str],
) -> dict[str, BaggageItem]:
    """Build the updated baggage register atomically."""

    result = {}
    seen_existing = set()

    for _, row in edited.iterrows():
        description = str(row.get("Description") or "").strip()

        raw_id = row.get("ID")
        record_id = str(raw_id) if pd.notna(raw_id) and str(raw_id).strip() else ""

        weight = _weight(row.get("Weight (kg)"))

        if not description:
            if weight is None and not record_id:
                continue

            raise ValueError("Every baggage row needs a description.")

        if record_id:
            if record_id not in existing:
                raise ValueError("Unknown baggage ID in edited table.")

            if record_id in seen_existing:
                raise ValueError("Duplicate baggage record.")

            seen_existing.add(record_id)
        else:
            record_id = uuid4().hex

        owner_label = row.get("Owner")

        if pd.isna(owner_label) or not owner_label:
            owner_label = "Unaccompanied"

        if owner_label not in owner_labels:
            raise ValueError(f"Unknown baggage owner: {owner_label}")

        owner_id = owner_labels[owner_label] or None

        if owner_id and owner_id not in passengers:
            # A passenger cannot be deleted while their
            # baggage still references them.
            raise ValueError(
                "A baggage owner was removed. Select another owner or Unaccompanied."
            )

        previous = existing.get(record_id)

        result[record_id] = BaggageItem(
            baggage_id=record_id,
            description=description,
            owner_passenger_id=owner_id,
            verified_weight=weight,
            weight_unit="kg",
            notes=previous.notes if previous else "",
        )

    return result


def apply_manifest_rows(
    edited_passengers: pd.DataFrame,
    edited_baggage: pd.DataFrame,
    existing_passengers: dict[str, Passenger],
    existing_baggage: dict[str, BaggageItem],
    owner_labels: dict[str, str],
) -> tuple[dict[str, Passenger], dict[str, BaggageItem]]:
    """Apply register edits with cascading passenger deletion.

    Deleting a passenger also deletes baggage belonging to that
    passenger. All validation occurs before the caller updates state.
    """

    new_passengers = apply_passenger_rows(
        edited_passengers,
        existing_passengers,
    )

    deleted_passenger_ids = set(existing_passengers) - set(new_passengers)

    # Baggage owned by a deleted passenger must also be deleted.
    cascade_baggage_ids = {
        baggage_id
        for baggage_id, item in existing_baggage.items()
        if item.owner_passenger_id in deleted_passenger_ids
    }

    remaining_baggage_rows = edited_baggage.copy()

    if cascade_baggage_ids:
        remaining_baggage_rows = remaining_baggage_rows.loc[
            ~remaining_baggage_rows["ID"].isin(cascade_baggage_ids)
        ].copy()

    new_baggage = apply_baggage_rows(
        remaining_baggage_rows,
        existing_baggage,
        new_passengers,
        owner_labels,
    )

    return new_passengers, new_baggage
