"""Interactive CG overview for multi-leg flight operations.

Shows independently assessed zero-fuel, departure, and arrival
loading conditions for each leg.

Connecting lines show endpoint differences only. They must not
be interpreted as verified continuous CG trajectories.

All information is for planning assessment, not flight approval.
"""

from pathlib import Path

import plotly.graph_objects as go

from flightops.operations.services.leg_cg_plots import OperationCGPlotResult
from flightops.weight_balance.plot_data import CGPlotLoadingPoint
from flightops.weight_balance.plotting import (
    STATUS_COLOURS,
    STATUS_LABELS,
)

ZFW_COLOUR = "#dc3545"
ARRIVAL_COLOUR = "#0d6efd"


def _hover_text(
    label: str,
    loading: CGPlotLoadingPoint,
) -> str:
    """Build hover information using an existing validation result."""

    lines = [
        f"<b>{label}</b>",
        f"Status: {STATUS_LABELS[loading.status]}",
        f"Weight: {loading.point.weight_kg:.2f} kg",
        f"CG: {loading.point.cg_mm:.2f} mm",
    ]

    if loading.weight_margin_kg is not None:
        lines.append(f"Weight margin: {loading.weight_margin_kg:.2f} kg")

    if loading.forward_margin_mm is not None:
        lines.append(f"Forward CG margin: {loading.forward_margin_mm:.2f} mm")

    if loading.aft_margin_mm is not None:
        lines.append(f"Aft CG margin: {loading.aft_margin_mm:.2f} mm")

    lines.extend(loading.findings)

    return "<br>".join(lines) + "<extra></extra>"


def _add_point(
    figure: go.Figure,
    loading: CGPlotLoadingPoint,
    *,
    name: str,
    colour: str,
    symbol: str,
) -> None:
    """Add one independently assessed loading condition."""

    figure.add_trace(
        go.Scatter(
            x=[loading.point.cg_mm],
            y=[loading.point.weight_kg],
            mode="markers",
            name=name,
            marker={
                "size": 12,
                "color": colour,
                "symbol": symbol,
                "line": {
                    "color": "#212529",
                    "width": 1,
                },
            },
            hovertemplate=_hover_text(name, loading),
        )
    )


def _add_endpoint_line(
    figure: go.Figure,
    start: CGPlotLoadingPoint,
    end: CGPlotLoadingPoint,
    *,
    name: str,
    colour: str,
) -> None:
    """Connect calculated endpoints without implying a continuous path."""

    figure.add_trace(
        go.Scatter(
            x=[
                start.point.cg_mm,
                end.point.cg_mm,
            ],
            y=[
                start.point.weight_kg,
                end.point.weight_kg,
            ],
            mode="lines",
            name=name,
            line={
                "color": colour,
                "width": 2,
                "dash": "dot",
            },
            hoverinfo="skip",
            showlegend=False,
        )
    )


def create_operation_cg_overview(
    operation: OperationCGPlotResult,
) -> go.Figure:
    """Create one CG envelope figure containing every flight leg."""

    if not operation.legs:
        raise ValueError("Cannot create a CG overview without flight legs.")

    reference = operation.legs[0].plot

    for leg in operation.legs:
        plot = leg.plot

        if (
            plot.aircraft_profile_id != operation.aircraft_profile_id
            or plot.configuration_revision_id != operation.configuration_revision_id
            or plot.configuration_revision_number
            != reference.configuration_revision_number
        ):
            raise ValueError("CG overview contains inconsistent aircraft revisions.")

        if plot.envelope != reference.envelope:
            raise ValueError("CG overview contains inconsistent CG envelopes.")

    figure = go.Figure()

    envelope = reference.envelope

    if envelope is not None:
        polygon = envelope.polygon

        if polygon:
            closed_polygon = (*polygon, polygon[0])

            figure.add_trace(
                go.Scatter(
                    x=[point.cg_mm for point in closed_polygon],
                    y=[point.weight_kg for point in closed_polygon],
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(25, 135, 84, 0.10)",
                    line={
                        "color": "#198754",
                        "width": 2,
                    },
                    name="Configured CG envelope",
                    hoverinfo="skip",
                )
            )

    for leg in operation.legs:
        plot = leg.plot

        if not plot.loading_points:
            raise ValueError(f"Leg '{leg.leg_id}' has no departure assessment.")

        if plot.zero_fuel_assessment is None or plot.arrival_assessment is None:
            raise ValueError(f"Leg '{leg.leg_id}' is missing a loading assessment.")

        zfw = plot.zero_fuel_assessment
        departure = plot.loading_points[0]
        arrival = plot.arrival_assessment

        if plot.zero_fuel_point is not None and plot.zero_fuel_point != zfw.point:
            raise ValueError(f"Leg '{leg.leg_id}' has inconsistent ZFW coordinates.")

        prefix = f"Leg {leg.sequence_number}"

        _add_endpoint_line(
            figure,
            zfw,
            departure,
            name=f"{prefix} fuel-loading endpoints",
            colour="#6c757d",
        )

        _add_endpoint_line(
            figure,
            departure,
            arrival,
            name=f"{prefix} fuel-burn endpoints",
            colour="#0d6efd",
        )

        _add_point(
            figure,
            zfw,
            name=f"{prefix} ZFW",
            colour=ZFW_COLOUR,
            symbol="circle",
        )

        _add_point(
            figure,
            departure,
            name=f"{prefix} Departure",
            colour=STATUS_COLOURS[departure.status],
            symbol="square",
        )

        _add_point(
            figure,
            arrival,
            name=f"{prefix} Arrival",
            colour=ARRIVAL_COLOUR,
            symbol="diamond",
        )

    figure.update_layout(
        title={
            "text": (
                "Flight Operation — Longitudinal CG Overview"
                "<br><sup>"
                f"Operation: {operation.operation_id} | "
                f"Aircraft: {operation.aircraft_profile_id} | "
                f"Configuration revision: "
                f"{reference.configuration_revision_number}"
                "</sup>"
            ),
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis_title="Longitudinal CG (mm)",
        yaxis_title="Aircraft Weight (kg)",
        template="plotly_white",
        hovermode="closest",
        legend={
            "orientation": "h",
            "y": -0.18,
        },
        margin={
            "l": 70,
            "r": 40,
            "t": 110,
            "b": 110,
        },
        annotations=[
            {
                "text": (
                    "Planning assessment only — "
                    "connecting lines show calculated endpoints, "
                    "not verified CG trajectories."
                ),
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": -0.32,
                "showarrow": False,
                "font": {
                    "size": 11,
                    "color": "#6c757d",
                },
            }
        ],
    )

    return figure


def export_operation_cg_overview(
    operation: OperationCGPlotResult,
    output_path: str | Path,
) -> Path:
    """Export a self-contained interactive HTML overview."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    figure = create_operation_cg_overview(operation)

    figure.write_html(
        str(path),
        include_plotlyjs=True,
        full_html=True,
        auto_open=False,
    )

    return path
