"""Interactive longitudinal CG envelope rendering.

Plotting is a presentation layer only. It must not independently
calculate weight-and-balance results or determine compliance.
"""

from pathlib import Path

import plotly.graph_objects as go

from flightops.weight_balance.plot_data import CGPlotData, WBPlotStatus

STATUS_COLOURS = {
    WBPlotStatus.WITHIN_LIMITS: "#198754",
    WBPlotStatus.OUTSIDE_LIMITS: "#dc3545",
    WBPlotStatus.INCOMPLETE: "#ffc107",
    WBPlotStatus.DEVELOPMENT: "#6f42c1",
}

STATUS_LABELS = {
    WBPlotStatus.WITHIN_LIMITS: "Within configured limits",
    WBPlotStatus.OUTSIDE_LIMITS: "Outside configured limits",
    WBPlotStatus.INCOMPLETE: "Assessment incomplete",
    WBPlotStatus.DEVELOPMENT: "Development assessment only",
}


def _format_margin(value: float | None, unit: str) -> str:
    if value is None:
        return "Not available"
    return f"{value:.2f} {unit}"


def _add_arrival_assessment(
    figure: go.Figure,
    data: CGPlotData,
) -> None:
    """Add the independently assessed arrival loading condition."""

    arrival = data.arrival_assessment

    if arrival is None:
        return

    if not data.loading_points:
        raise ValueError("An arrival assessment requires a departure loading point.")

    departure = data.loading_points[0]

    # This joins the calculated endpoints. It is not a certified
    # continuous fuel-consumption CG trajectory.
    figure.add_trace(
        go.Scatter(
            x=[
                departure.point.cg_mm,
                arrival.point.cg_mm,
            ],
            y=[
                departure.point.weight_kg,
                arrival.point.weight_kg,
            ],
            mode="lines",
            name="Planned fuel-burn endpoint trend",
            line={
                "color": "#0d6efd",
                "width": 2,
                "dash": "dash",
            },
            hoverinfo="skip",
        )
    )

    status = STATUS_LABELS[arrival.status]

    hover_lines = [
        "<b>Arrival Weight</b>",
        f"Status: {status}",
        f"Weight: {arrival.point.weight_kg:.2f} kg",
        f"CG: {arrival.point.cg_mm:.2f} mm",
        ("Weight margin: " + _format_margin(arrival.weight_margin_kg, "kg")),
        ("Forward CG margin: " + _format_margin(arrival.forward_margin_mm, "mm")),
        ("Aft CG margin: " + _format_margin(arrival.aft_margin_mm, "mm")),
        *arrival.findings,
    ]

    figure.add_trace(
        go.Scatter(
            x=[arrival.point.cg_mm],
            y=[arrival.point.weight_kg],
            mode="markers+text",
            text=["Arrival"],
            textposition="top center",
            marker={
                "size": 13,
                "color": "#0d6efd",
                "symbol": "diamond",
                "line": {
                    "color": "#212529",
                    "width": 1,
                },
            },
            name="Arrival Weight",
            hovertemplate=("<br>".join(hover_lines) + "<extra></extra>"),
        )
    )


def create_cg_figure(data: CGPlotData) -> go.Figure:
    """Render validated CG plotting data as an interactive figure."""

    figure = go.Figure()

    if data.envelope is not None:
        polygon = data.envelope.polygon

        if polygon:
            closed_polygon = (*polygon, polygon[0])

            figure.add_trace(
                go.Scatter(
                    x=[point.cg_mm for point in closed_polygon],
                    y=[point.weight_kg for point in closed_polygon],
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(25, 135, 84, 0.12)",
                    line={
                        "color": "rgba(25, 135, 84, 0.45)",
                        "width": 1,
                    },
                    name="Configured CG envelope",
                    hoverinfo="skip",
                )
            )

        figure.add_trace(
            go.Scatter(
                x=[point.cg_mm for point in data.envelope.forward_boundary],
                y=[point.weight_kg for point in data.envelope.forward_boundary],
                mode="lines+markers",
                name="Forward CG limit",
                line={"color": "#0d6efd", "width": 2},
            )
        )

        figure.add_trace(
            go.Scatter(
                x=[point.cg_mm for point in data.envelope.aft_boundary],
                y=[point.weight_kg for point in data.envelope.aft_boundary],
                mode="lines+markers",
                name="Aft CG limit",
                line={"color": "#fd7e14", "width": 2},
            )
        )
    if data.zero_fuel_point is not None:
        zfw = data.zero_fuel_point
        zfw_assessment = data.zero_fuel_assessment

        if zfw_assessment is not None:
            if zfw_assessment.point != zfw:
                raise ValueError(
                    "Zero-fuel plotting coordinates do not match "
                    "the validated zero-fuel assessment."
                )

            zfw_status = STATUS_LABELS[zfw_assessment.status]

            zfw_findings = (
                "<br>".join(zfw_assessment.findings)
                if zfw_assessment.findings
                else "No additional findings"
            )

            zfw_hover = "<br>".join(
                [
                    "<b>Zero-Fuel Weight</b>",
                    f"Status: {zfw_status}",
                    f"Weight: {zfw.weight_kg:.2f} kg",
                    f"CG: {zfw.cg_mm:.2f} mm",
                    (
                        "Weight margin: "
                        + _format_margin(
                            zfw_assessment.weight_margin_kg,
                            "kg",
                        )
                    ),
                    (
                        "Forward CG margin: "
                        + _format_margin(
                            zfw_assessment.forward_margin_mm,
                            "mm",
                        )
                    ),
                    (
                        "Aft CG margin: "
                        + _format_margin(
                            zfw_assessment.aft_margin_mm,
                            "mm",
                        )
                    ),
                    f"Findings: {zfw_findings}",
                ]
            )
        else:
            zfw_hover = "<br>".join(
                [
                    "<b>Zero-Fuel Weight</b>",
                    "Status: Not independently assessed",
                    f"Weight: {zfw.weight_kg:.2f} kg",
                    f"CG: {zfw.cg_mm:.2f} mm",
                ]
            )

        # Draw the fuel-loading trend between ZFW and takeoff.
        if data.loading_points:
            takeoff = data.loading_points[0].point

            figure.add_trace(
                go.Scatter(
                    x=[zfw.cg_mm, takeoff.cg_mm],
                    y=[zfw.weight_kg, takeoff.weight_kg],
                    mode="lines",
                    name="Fuel loading trend",
                    line={
                        "color": "#6c757d",
                        "width": 2,
                        "dash": "dash",
                    },
                    hoverinfo="skip",
                )
            )

        # Always display the zero-fuel point in red.
        figure.add_trace(
            go.Scatter(
                x=[zfw.cg_mm],
                y=[zfw.weight_kg],
                mode="markers+text",
                text=["Zero Fuel"],
                textposition="bottom center",
                marker={
                    "size": 13,
                    "color": "#dc3545",
                    "line": {
                        "color": "#212529",
                        "width": 1,
                    },
                },
                name="Zero-Fuel Weight",
                hovertemplate=zfw_hover + "<extra></extra>",
            )
        )
    for loading in data.loading_points:
        colour = STATUS_COLOURS[loading.status]

        hover_text = "<br>".join(
            [
                f"<b>{loading.label}</b>",
                f"Status: {STATUS_LABELS[loading.status]}",
                f"Weight: {loading.point.weight_kg:.2f} kg",
                f"CG: {loading.point.cg_mm:.2f} mm",
                ("Weight margin: " + _format_margin(loading.weight_margin_kg, "kg")),
                (
                    "Forward CG margin: "
                    + _format_margin(loading.forward_margin_mm, "mm")
                ),
                ("Aft CG margin: " + _format_margin(loading.aft_margin_mm, "mm")),
                *loading.findings,
            ]
        )

        figure.add_trace(
            go.Scatter(
                x=[loading.point.cg_mm],
                y=[loading.point.weight_kg],
                mode="markers+text",
                text=[loading.label],
                textposition="top center",
                marker={
                    "size": 13,
                    "color": colour,
                    "line": {"color": "#212529", "width": 1},
                },
                name=loading.label,
                hovertemplate=hover_text + "<extra></extra>",
            )
        )
    _add_arrival_assessment(
        figure,
        data,
    )
    figure.update_layout(
        title=(
            "Longitudinal CG Envelope"
            "<br><sup>"
            f"Aircraft: {data.aircraft_profile_id} | "
            f"Revision: {data.configuration_revision_number} | "
            f"Verification: {data.verification_level.value}"
            "</sup>"
        ),
        xaxis_title="Longitudinal CG (mm)",
        yaxis_title="Aircraft Weight (kg)",
        template="plotly_white",
        hovermode="closest",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 70, "r": 40, "t": 100, "b": 90},
        annotations=[
            {
                "text": ("Assessment only — not an operational flight approval"),
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": -0.28,
                "showarrow": False,
                "font": {"size": 11, "color": "#6c757d"},
            }
        ],
    )

    return figure


def export_cg_html(
    data: CGPlotData,
    output_path: str | Path,
) -> Path:
    """Export a self-contained HTML graph for offline viewing."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    figure = create_cg_figure(data)

    figure.write_html(
        str(path),
        include_plotlyjs=True,
        full_html=True,
        auto_open=False,
    )

    return path
