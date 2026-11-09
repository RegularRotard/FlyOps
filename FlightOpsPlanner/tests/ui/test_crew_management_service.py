"""Tests for FlyOps crew-management validation."""

from datetime import date

import pytest

from app.crew_management_service import (
    CrewManagementError,
    build_pilot_record,
    normalise_variant_ids,
    parse_optional_date,
    pilot_warnings,
)


def pilot_data():
    return {
        "pilot_id": "P001",
        "full_name": "Development Pilot",
        "weight_kg": 85,
        "licence_type": "CPL(H)",
        "licence_number": "DEMO",
        "medical_expiry": "2027-06-30",
        "weight_verified_on": "2026-06-01",
        "qualified_variant_ids": ["VARIANT-A"],
        "active": True,
    }


def test_create_pilot():
    pilot = build_pilot_record(**pilot_data())

    assert pilot.full_name == "Development Pilot"
    assert pilot.weight_kg == 85


def test_missing_name_rejected():
    data = pilot_data()
    data["full_name"] = ""

    with pytest.raises(CrewManagementError):
        build_pilot_record(**data)


def test_invalid_weight_rejected():
    data = pilot_data()
    data["weight_kg"] = -5

    with pytest.raises(CrewManagementError):
        build_pilot_record(**data)


def test_missing_weight_rejected():
    data = pilot_data()
    data["weight_kg"] = None

    with pytest.raises(CrewManagementError):
        build_pilot_record(**data)


def test_optional_date():
    assert (
        parse_optional_date(
            "",
            "Medical",
        )
        is None
    )


def test_invalid_date():
    with pytest.raises(CrewManagementError):
        parse_optional_date(
            "31/12/2027",
            "Medical",
        )


def test_qualification_duplicates_removed():
    assert normalise_variant_ids(["A", "A", "B"]) == ("A", "B")


def test_expired_medical_warning():
    data = pilot_data()
    data["medical_expiry"] = "2025-01-01"

    pilot = build_pilot_record(**data)

    warnings = pilot_warnings(
        pilot,
        on_date=date(2026, 11, 10),
    )

    assert any("expired" in warning.lower() for warning in warnings)


def test_missing_qualification_warning():
    pilot = build_pilot_record(**pilot_data())

    warnings = pilot_warnings(
        pilot,
        variant_id="VARIANT-B",
        on_date=date(2026, 11, 10),
    )

    assert any("qualification" in warning.lower() for warning in warnings)


def test_inactive_pilot_warning():
    data = pilot_data()
    data["active"] = False

    pilot = build_pilot_record(**data)

    warnings = pilot_warnings(pilot)

    assert any("inactive" in warning.lower() for warning in warnings)
