"""Validation and editing helpers for FlyOps crew management."""

from datetime import date

from flightops.crew.roster import PilotRecord


class CrewManagementError(ValueError):
    """Invalid crew-management input."""


def parse_optional_date(
    value: str | None,
    field_name: str,
) -> date | None:
    """Parse an optional ISO-format date."""

    if value is None or not value.strip():
        return None

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise CrewManagementError(f"{field_name} must use YYYY-MM-DD.") from exc


def normalise_variant_ids(
    variant_ids,
) -> tuple[str, ...]:
    """Remove duplicate and empty qualification identifiers."""

    return tuple(
        dict.fromkeys(str(value).strip() for value in variant_ids if str(value).strip())
    )


def build_pilot_record(
    *,
    pilot_id: str,
    full_name: str,
    weight_kg: float,
    licence_type: str,
    licence_number: str,
    medical_expiry: str | None,
    weight_verified_on: str | None,
    qualified_variant_ids,
    active: bool,
) -> PilotRecord:
    """Construct one validated pilot record."""

    name = full_name.strip()

    if not name:
        raise CrewManagementError("Pilot name is required.")

    try:
        weight = float(weight_kg)
    except (TypeError, ValueError) as exc:
        raise CrewManagementError("Pilot weight must be numeric.") from exc

    try:
        return PilotRecord(
            pilot_id=pilot_id,
            full_name=name,
            weight_kg=weight,
            licence_type=licence_type.strip(),
            licence_number=licence_number.strip(),
            medical_expiry=parse_optional_date(
                medical_expiry,
                "Medical expiry",
            ),
            weight_verified_on=parse_optional_date(
                weight_verified_on,
                "Weight verification date",
            ),
            qualified_variant_ids=normalise_variant_ids(qualified_variant_ids),
            active=active,
        )

    except ValueError as exc:
        raise CrewManagementError(str(exc)) from exc


def pilot_warnings(
    pilot: PilotRecord,
    *,
    variant_id: str | None = None,
    on_date: date | None = None,
) -> tuple[str, ...]:
    """Return advisory warnings from recorded pilot information."""

    today = on_date or date.today()

    warnings = []

    if not pilot.active:
        warnings.append("Pilot is inactive.")

    if not pilot.licence_type:
        warnings.append("Licence type is not recorded.")

    if not pilot.licence_number:
        warnings.append("Licence number is not recorded.")

    if pilot.medical_expiry is None:
        warnings.append("Medical expiry is not recorded.")

    elif pilot.medical_expiry < today:
        warnings.append("Recorded medical has expired.")

    if pilot.weight_verified_on is None:
        warnings.append("Pilot weight has no verification date.")

    elif pilot.weight_verified_on > today:
        warnings.append("Weight verification date is in the future.")

    if variant_id is not None and variant_id not in pilot.qualified_variant_ids:
        warnings.append(
            "Aircraft qualification is not recorded for the selected variant."
        )

    return tuple(warnings)
