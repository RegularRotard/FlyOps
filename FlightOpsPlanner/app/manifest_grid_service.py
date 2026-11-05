"""Apply edited AG Grid manifest values to existing records."""

from dataclasses import dataclass
from math import isfinite

import pandas as pd

from app.manifest_live import (
    update_baggage,
    update_passenger,
)


class ManifestGridError(ValueError):
    """Raised when an edited manifest contains invalid data."""


@dataclass(frozen=True)
class GridRegisterResult:
    passengers: dict
    baggage: dict


def _parse_weight(value):
    """Accept a missing weight or a valid nonnegative number."""

    if value is None or pd.isna(value):
        return None

    if isinstance(value, str) and not value.strip():
        return None

    try:
        weight = float(value)
    except (ValueError, TypeError) as exc:
        raise ManifestGridError("Weight must be numeric.") from exc

    if not isfinite(weight) or weight < 0:
        raise ManifestGridError("Weight must be finite and nonnegative.")

    return weight


def apply_grid_edits(
    edited_rows: pd.DataFrame,
    passengers: dict,
    baggage: dict,
) -> GridRegisterResult:
    """Apply edited descriptions and weights using stable record IDs.

    All edits are validated before updated registers are returned.
    Creation and deletion are handled separately.
    """

    updated_passengers = dict(passengers)
    updated_baggage = dict(baggage)

    for _, row in edited_rows.iterrows():
        record_id = str(row["ID"])

        description = str(row["Description"]).strip()

        if not description:
            raise ManifestGridError("Names and descriptions cannot be empty.")

        weight = _parse_weight(row["Weight (kg)"])

        if record_id in updated_passengers:
            updated_passengers[record_id] = update_passenger(
                updated_passengers[record_id],
                name=description,
                weight_kg=weight,
            )

        elif record_id in updated_baggage:
            updated_baggage[record_id] = update_baggage(
                updated_baggage[record_id],
                description=clean_baggage_description(description),
                weight_kg=weight,
            )

        else:
            raise ManifestGridError(f"Unknown manifest record: {record_id}")

    return GridRegisterResult(
        passengers=updated_passengers,
        baggage=updated_baggage,
    )


def resolve_baggage_owner(
    selected_id: str | None,
    passengers: dict,
    baggage: dict,
) -> str | None:
    """Find the passenger to own newly added baggage."""

    if selected_id in passengers:
        return selected_id

    selected_baggage = baggage.get(selected_id)

    if selected_baggage is not None:
        owner_id = selected_baggage.owner_passenger_id

        if owner_id in passengers:
            return owner_id

    if passengers:
        return next(reversed(passengers))

    return None


def clean_baggage_description(description: str) -> str:
    """Remove legacy UI-only baggage indentation.

    The register stores the actual description, never visual
    indentation characters.
    """

    description = description.strip()

    while description.startswith("↳"):
        description = description[1:].lstrip()

    return description
