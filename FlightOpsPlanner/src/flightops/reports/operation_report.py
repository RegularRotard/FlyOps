"""Offline HTML reports for planned helicopter flight operations.

Reports present existing operation data, calculated W&B results,
and validation findings.

They are not operational flight-release authorisations.
"""

from html import escape
from pathlib import Path

from flightops.fuel.display import (
    FuelDisplayBasis,
    display_fuel,
)
from flightops.operations.schemas.flight import FlightOperation
from flightops.operations.services.leg_weight_balance import (
    OperationWeightBalanceResult,
)
from flightops.operations.services.operation_assessment import (
    OperationAssessmentResult,
    OperationAssessmentStatus,
)

STATUS_COLOURS = {
    OperationAssessmentStatus.PASS: "#198754",
    OperationAssessmentStatus.FAIL: "#dc3545",
    OperationAssessmentStatus.INCOMPLETE: "#b8860b",
    OperationAssessmentStatus.DEVELOPMENT: "#6f42c1",
}


def _safe(value: object) -> str:
    """Escape user-supplied values for HTML output."""
    return escape(str(value), quote=True)


def _weight(value: float) -> str:
    return f"{value:.2f} kg"


def _cg(value: float) -> str:
    return f"{value:.2f} mm"


def _status_badge(status: OperationAssessmentStatus) -> str:
    colour = STATUS_COLOURS[status]

    return (
        f'<span class="status" style="background:{colour}">'
        f"{_safe(status.value.upper())}"
        "</span>"
    )


def _validate_report_inputs(
    operation: FlightOperation,
    calculations: OperationWeightBalanceResult,
    assessment: OperationAssessmentResult,
) -> None:
    """Reject mismatched operation records and calculation results."""

    expected = (
        operation.operation_id,
        operation.aircraft_profile_id,
        operation.configuration_revision_id,
    )

    calculated = (
        calculations.operation_id,
        calculations.aircraft_profile_id,
        calculations.configuration_revision_id,
    )

    assessed = (
        assessment.operation_id,
        assessment.aircraft_profile_id,
        assessment.configuration_revision_id,
    )

    if expected != calculated or expected != assessed:
        raise ValueError(
            "Report inputs reference different operations, "
            "aircraft, or configuration revisions."
        )

    operation_legs = [(leg.leg_id, leg.sequence_number) for leg in operation.legs]

    calculated_legs = [(leg.leg_id, leg.sequence_number) for leg in calculations.legs]

    assessed_legs = [(leg.leg_id, leg.sequence_number) for leg in assessment.legs]

    if operation_legs != calculated_legs or operation_legs != assessed_legs:
        raise ValueError("Report input flight legs do not match.")

    if not assessment.fuel_continuity_verified:
        raise ValueError("Fuel continuity must be verified before report generation.")

    expected_transitions = [
        (previous.leg_id, current.leg_id)
        for previous, current in zip(
            operation.legs,
            operation.legs[1:],
        )
    ]

    actual_transitions = [
        (transition.after_leg_id, transition.before_leg_id)
        for transition in calculations.fuel_continuity.transitions
    ]

    if expected_transitions != actual_transitions:
        raise ValueError("Fuel-continuity transitions do not match the flight legs.")


def _manifest_rows(leg) -> str:
    """Generate the crew, passenger, baggage, and cargo manifest."""

    if not leg.loads:
        return '<tr><td colspan="5">No additional loads recorded</td></tr>'

    rows = []

    for load in leg.loads:
        rows.append(
            "<tr>"
            f"<td>{_safe(load.category.value)}</td>"
            f"<td>{_safe(load.name)}</td>"
            f"<td>{_safe(load.person_id or '—')}</td>"
            f"<td>{_safe(load.station_id)}</td>"
            f"<td>{_weight(load.weight_kg)}</td>"
            "</tr>"
        )

    return "\n".join(rows)


def _fuel_rows(
    leg,
    basis: FuelDisplayBasis,
) -> str:
    """Generate fuel planning records with simultaneous units."""

    if not leg.fuel.tanks:
        return '<tr><td colspan="4">No fuel tanks recorded</td></tr>'

    rows = []

    for tank in leg.fuel.tanks:
        rows.append(
            "<tr>"
            f"<td>{_safe(tank.station_id)}</td>"
            f"<td>{_safe(display_fuel(tank.departure_fuel_kg, FuelDisplayBasis(density_kg_per_litre=basis.density_kg_per_litre)).formatted)}</td>"
            f"<td>{_safe(display_fuel(tank.planned_burn_kg, FuelDisplayBasis(density_kg_per_litre=basis.density_kg_per_litre)).formatted)}</td>"
            f"<td>{_safe(display_fuel(tank.arrival_fuel_kg, FuelDisplayBasis(density_kg_per_litre=basis.density_kg_per_litre)).formatted)}</td>"
            "</tr>"
        )

    rows.append(
        "<tr>"
        "<th>Total fuel</th>"
        f"<th>{_safe(display_fuel(leg.fuel.departure_fuel_kg, basis).formatted)}</th>"
        f"<th>{_safe(display_fuel(leg.fuel.planned_burn_kg, basis).formatted)}</th>"
        f"<th>{_safe(display_fuel(leg.fuel.arrival_fuel_kg, basis).formatted)}</th>"
        "</tr>"
    )

    return "\n".join(rows)


def _wb_rows(calculation, summary) -> str:
    """Generate the three independently assessed loading conditions."""

    conditions = (
        ("Zero fuel", calculation.zero_fuel, summary.zero_fuel_status),
        ("Departure", calculation.departure, summary.departure_status),
        ("Arrival", calculation.arrival, summary.arrival_status),
    )

    rows = []

    for label, result, status in conditions:
        validation = result.validation

        rows.append(
            "<tr>"
            f"<td>{_safe(label)}</td>"
            f"<td>{_weight(validation.total_weight_kg)}</td>"
            f"<td>{_cg(validation.cg_mm)}</td>"
            f"<td>{_status_badge(status)}</td>"
            "</tr>"
        )

    return "\n".join(rows)


def _findings_rows(summary) -> str:
    if not summary.findings:
        return "<li>No additional assessment findings recorded.</li>"

    return "\n".join(
        "<li>"
        f"<strong>{_safe(finding.condition.value)}:</strong> "
        f"{_safe(finding.message)}"
        "</li>"
        for finding in summary.findings
    )


def _refuelling_section(calculations) -> str:
    rows = []

    for transition in calculations.fuel_continuity.transitions:
        for tank in transition.tanks:
            rows.append(
                "<tr>"
                f"<td>{_safe(transition.after_leg_id)}</td>"
                f"<td>{_safe(transition.before_leg_id)}</td>"
                f"<td>{_safe(tank.station_id)}</td>"
                f"<td>{_weight(tank.previous_arrival_kg)}</td>"
                f"<td>{_weight(tank.refuelled_kg)}</td>"
                f"<td>{_weight(tank.planned_departure_kg)}</td>"
                "</tr>"
            )

    if not rows:
        rows.append('<tr><td colspan="6">No inter-leg fuel transitions</td></tr>')

    return f"""
    <section>
        <h2>Fuel Continuity and Refuelling</h2>
        <table>
            <thead>
                <tr>
                    <th>After leg</th>
                    <th>Before leg</th>
                    <th>Fuel station</th>
                    <th>Previous arrival</th>
                    <th>Refuelled</th>
                    <th>Next departure</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    </section>
    """


def render_operation_report(
    operation: FlightOperation,
    calculations: OperationWeightBalanceResult,
    assessment: OperationAssessmentResult,
    *,
    fuel_basis: FuelDisplayBasis | None = None,
) -> str:
    """Render a complete, printable HTML flight operations report."""
    if fuel_basis is None:
        fuel_basis = FuelDisplayBasis()

    _validate_report_inputs(
        operation,
        calculations,
        assessment,
    )

    leg_sections = []

    for leg, calculation, summary in zip(
        operation.legs,
        calculations.legs,
        assessment.legs,
        strict=True,
    ):
        leg_sections.append(
            f"""
            <section>
                <h2>
                    Leg {leg.sequence_number}:
                    {_safe(leg.departure.location_id)}
                    →
                    {_safe(leg.destination.location_id)}
                </h2>

                <p><strong>Leg ID:</strong> {_safe(leg.leg_id)}</p>
                <p>
                    <strong>Loading assessment:</strong>
                    {_status_badge(summary.status)}
                </p>

                <h3>Manifest and Loads</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th>Name</th>
                            <th>Person ID</th>
                            <th>Station</th>
                            <th>Weight</th>
                        </tr>
                    </thead>
                    <tbody>{_manifest_rows(leg)}</tbody>
                </table>

                <h3>Fuel Planning</h3>
                <p>
                    <strong>Fuel density:</strong>
                    {
                f"{fuel_basis.density_kg_per_litre:.3f} kg/L"
                if fuel_basis.density_kg_per_litre is not None
                else "Not specified"
            }
                    <br>
                    <strong>Fuel consumption:</strong>
                    {
                f"{fuel_basis.consumption_kg_per_hour:.1f} kg/h"
                if fuel_basis.consumption_kg_per_hour is not None
                else "Not specified"
            }
                    <br>
                    <small>
                        Fuel minutes represent equivalent duration at
                        the specified consumption rate, not guaranteed
                        usable flight endurance.
                    </small>
                </p>
                <table>
                    <thead>
                        <tr>
                            <th>Tank</th>
                            <th>Departure</th>
                            <th>Planned burn</th>
                            <th>Arrival</th>
                        </tr>
                    </thead>
                    <tbody>{_fuel_rows(leg, fuel_basis)}</tbody>
                </table>

                <h3>Weight and Balance</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Condition</th>
                            <th>Weight</th>
                            <th>Longitudinal CG</th>
                            <th>Assessment</th>
                        </tr>
                    </thead>
                    <tbody>{_wb_rows(calculation, summary)}</tbody>
                </table>

                <h3>Assessment Findings</h3>
                <ul>{_findings_rows(summary)}</ul>
            </section>
            """
        )

    status = assessment.status

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>FlyOps — {_safe(operation.operation_id)}</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            max-width: 1100px;
            margin: 30px auto;
            padding: 0 24px;
            color: #212529;
            line-height: 1.5;
        }}

        h1, h2, h3 {{ color: #17324d; }}

        header {{
            border-bottom: 3px solid #17324d;
            margin-bottom: 24px;
        }}

        section {{
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            break-inside: avoid;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0 22px;
            font-size: 13px;
        }}

        th, td {{
            border: 1px solid #dee2e6;
            padding: 9px;
            text-align: left;
        }}

        th {{ background: #edf2f7; }}

        .status {{
            color: white;
            border-radius: 4px;
            padding: 3px 8px;
            font-weight: bold;
            font-size: 12px;
        }}

        .warning {{
            padding: 14px;
            border-left: 4px solid #dc3545;
            background: #fff3f3;
            margin: 20px 0;
        }}

        @media print {{
            body {{ margin: 0; padding: 0; }}
            section {{ border: none; }}
            header {{ break-after: avoid; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>FlyOps — Flight Operations Report</h1>
        <p><strong>Operation:</strong> {_safe(operation.operation_id)}</p>
        <p><strong>Aircraft profile:</strong>
            {_safe(operation.aircraft_profile_id)}</p>
        <p><strong>Configuration revision:</strong>
            {_safe(operation.configuration_revision_id)}</p>
        <p><strong>Overall loading assessment:</strong>
            {_status_badge(status)}</p>
    </header>

    <div class="warning">
        <strong>Planning document — not flight-release approval.</strong>
        <br>
        This report contains calculated loading assessments based on
        configured aircraft data. It does not establish compliance with
        all applicable operational, regulatory, fuel-reserve, aircraft
        performance, or flight-release requirements.
    </div>

    {"".join(leg_sections)}

    {_refuelling_section(calculations)}

    <footer>
        <p>
            Generated by FlyOps.
            Aircraft configuration and calculation records must remain
            traceable to their approved source documentation.
        </p>
    </footer>
</body>
</html>
"""


def export_operation_report(
    operation: FlightOperation,
    calculations: OperationWeightBalanceResult,
    assessment: OperationAssessmentResult,
    output_path: str | Path,
    *,
    fuel_basis: FuelDisplayBasis | None = None,
) -> Path:
    """Export the printable HTML report to a local file."""

    html = render_operation_report(
        operation,
        calculations,
        assessment,
        fuel_basis=fuel_basis,
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(html, encoding="utf-8")

    return path
