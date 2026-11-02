"""Tests for offline flight operations HTML reports."""

from dataclasses import replace

import pytest

from flightops.fuel.display import FuelDisplayBasis
from flightops.operations.schemas.flight import FlightOperation
from flightops.operations.services.leg_weight_balance import (
    calculate_operation_weight_balance,
)
from flightops.operations.services.operation_assessment import (
    assess_operation_weight_balance,
)
from flightops.reports.operation_report import (
    export_operation_report,
    render_operation_report,
)
from tests.operations.test_leg_weight_balance import make_leg
from tests.weight_balance.test_revision_bound_validation import aircraft
from tests.weight_balance.test_zero_fuel import configured_revision


def report_inputs():
    revision = configured_revision()
    profile = aircraft()

    operation = FlightOperation(
        operation_id="FO-REPORT-001",
        aircraft_profile_id=profile.id,
        configuration_revision_id=revision.id,
        legs=[
            make_leg(
                number=1,
                origin="HTZA",
                destination="HTDA",
                fuel_kg=60,
                burn_kg=20,
                baggage_kg=25,
            ),
            make_leg(
                number=2,
                origin="HTDA",
                destination="HTPE",
                fuel_kg=40,
                burn_kg=15,
            ),
        ],
    )

    calculations = calculate_operation_weight_balance(
        operation,
        revision,
        profile,
    )

    assessment = assess_operation_weight_balance(calculations)

    return operation, calculations, assessment


def test_report_contains_operation_identity():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "FO-REPORT-001" in html
    assert operation.aircraft_profile_id in html
    assert operation.configuration_revision_id in html


def test_report_contains_each_flight_leg():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Leg 1:" in html
    assert "Leg 2:" in html
    assert "HTZA" in html
    assert "HTDA" in html
    assert "HTPE" in html


def test_report_contains_loading_conditions():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Zero fuel" in html
    assert "Departure" in html
    assert "Arrival" in html
    assert "Longitudinal CG" in html


def test_report_contains_fuel_planning():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Fuel Planning" in html
    assert "Planned burn" in html
    assert "Fuel Continuity and Refuelling" in html


def test_report_contains_manifest():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Manifest and Loads" in html
    assert "Baggage" in html


def test_report_contains_assessment_status():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Overall loading assessment" in html
    assert assessment.status.value.upper() in html


def test_report_contains_operational_warning():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "not flight-release approval" in html


def test_export_creates_html_file(tmp_path):
    operation, calculations, assessment = report_inputs()

    output = tmp_path / "operation_report.html"

    result = export_operation_report(
        operation,
        calculations,
        assessment,
        output,
    )

    assert result == output
    assert output.exists()
    assert "FO-REPORT-001" in output.read_text(encoding="utf-8")


def test_mismatched_operation_rejected():
    operation, calculations, assessment = report_inputs()

    wrong_operation = operation.model_copy(update={"operation_id": "WRONG-OPERATION"})

    with pytest.raises(ValueError, match="different operations"):
        render_operation_report(
            wrong_operation,
            calculations,
            assessment,
        )


def test_mismatched_flight_legs_rejected():
    operation, calculations, assessment = report_inputs()

    wrong_calculations = replace(
        calculations,
        legs=calculations.legs[:1],
    )

    with pytest.raises(ValueError, match="flight legs do not match"):
        render_operation_report(
            operation,
            wrong_calculations,
            assessment,
        )


def test_unverified_fuel_continuity_rejected():
    operation, calculations, assessment = report_inputs()

    bad_assessment = replace(
        assessment,
        fuel_continuity_verified=False,
    )

    with pytest.raises(ValueError, match="Fuel continuity"):
        render_operation_report(
            operation,
            calculations,
            bad_assessment,
        )


def test_html_escapes_user_supplied_text():
    operation, calculations, assessment = report_inputs()

    modified_leg = operation.legs[0].model_copy(
        update={
            "departure": operation.legs[0].departure.model_copy(
                update={"location_id": "<script>alert(1)</script>"}
            )
        }
    )

    modified_operation = operation.model_copy(
        update={"legs": [modified_leg, operation.legs[1]]}
    )

    html = render_operation_report(
        modified_operation,
        calculations,
        assessment,
    )

    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_report_displays_fuel_in_three_units():
    operation, calculations, assessment = report_inputs()

    basis = FuelDisplayBasis(
        density_kg_per_litre=0.8,
        consumption_kg_per_hour=72.0,
    )

    html = render_operation_report(
        operation,
        calculations,
        assessment,
        fuel_basis=basis,
    )

    assert "60.0 kg / 75.0 L / 50 min" in html
    assert "0.800 kg/L" in html
    assert "72.0 kg/h" in html


def test_report_does_not_invent_fuel_conversion_values():
    operation, calculations, assessment = report_inputs()

    html = render_operation_report(
        operation,
        calculations,
        assessment,
    )

    assert "Not specified" in html
    assert "N/A L" in html
    assert "N/A min" in html
