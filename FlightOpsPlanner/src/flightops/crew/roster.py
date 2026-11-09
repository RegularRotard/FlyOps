"""Persistent crew register for FlyOps.

Stored crew details support planning and credential review.
They do not independently establish fitness, currency or
authorization to conduct a flight.
"""

import json
from dataclasses import dataclass
from datetime import date
from math import isfinite
from pathlib import Path

ROSTER_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "aircraft" / "crew_roster.json"
)


@dataclass(frozen=True)
class PilotRecord:
    pilot_id: str
    full_name: str
    weight_kg: float
    licence_type: str
    licence_number: str
    medical_expiry: date | None
    qualified_variant_ids: tuple[str, ...]
    active: bool = True
    weight_verified_on: date | None = None

    def __post_init__(self):
        if not self.pilot_id.strip():
            raise ValueError("Pilot ID is required.")

        if not self.full_name.strip():
            raise ValueError("Pilot name is required.")

        if not isfinite(self.weight_kg) or self.weight_kg <= 0:
            raise ValueError("Pilot weight must be positive and finite.")

    def medical_status(
        self,
        *,
        on_date: date | None = None,
    ) -> str:
        if self.medical_expiry is None:
            return "NOT RECORDED"

        today = on_date or date.today()

        if self.medical_expiry < today:
            return "EXPIRED"

        return "RECORDED AS CURRENT"

    def qualified_for_variant(
        self,
        variant_id: str,
    ) -> bool:
        return variant_id in self.qualified_variant_ids


def load_pilots(
    path: Path = ROSTER_PATH,
) -> dict[str, PilotRecord]:
    """Load saved crew records."""

    if not path.exists():
        return {}

    records = json.loads(path.read_text(encoding="utf-8"))

    pilots = {}

    for record in records:
        pilot = PilotRecord(
            pilot_id=record["pilot_id"],
            full_name=record["full_name"],
            weight_kg=float(record["weight_kg"]),
            licence_type=record.get("licence_type", ""),
            licence_number=record.get("licence_number", ""),
            medical_expiry=(
                date.fromisoformat(record["medical_expiry"])
                if record.get("medical_expiry")
                else None
            ),
            qualified_variant_ids=tuple(
                record.get(
                    "qualified_variant_ids",
                    [],
                )
            ),
            active=record.get("active", True),
            weight_verified_on=(
                date.fromisoformat(record["weight_verified_on"])
                if record.get("weight_verified_on")
                else None
            ),
        )

        if pilot.pilot_id in pilots:
            raise ValueError(f"Duplicate pilot ID: {pilot.pilot_id}")

        pilots[pilot.pilot_id] = pilot

    return pilots


def save_pilots(
    pilots: dict[str, PilotRecord],
    path: Path = ROSTER_PATH,
) -> None:
    """Save the complete pilot register."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = []

    for pilot in pilots.values():
        records.append(
            {
                "pilot_id": pilot.pilot_id,
                "full_name": pilot.full_name,
                "weight_kg": pilot.weight_kg,
                "licence_type": pilot.licence_type,
                "licence_number": pilot.licence_number,
                "medical_expiry": (
                    pilot.medical_expiry.isoformat() if pilot.medical_expiry else None
                ),
                "qualified_variant_ids": list(pilot.qualified_variant_ids),
                "active": pilot.active,
                "weight_verified_on": (
                    pilot.weight_verified_on.isoformat()
                    if pilot.weight_verified_on
                    else None
                ),
            }
        )

    path.write_text(
        json.dumps(
            records,
            indent=2,
        ),
        encoding="utf-8",
    )
