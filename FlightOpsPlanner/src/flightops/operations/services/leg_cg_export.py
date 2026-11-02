"""Offline HTML export for per-leg aircraft CG graphs.

The exported graphs are planning assessments and do not
constitute operational flight-release authorisation.
"""

from pathlib import Path

from flightops.operations.services.leg_cg_plots import LegCGPlotResult
from flightops.weight_balance.plot_data import WBPlotStatus
from flightops.weight_balance.plotting import create_cg_figure


def _assessment_summary(loading) -> str:
    """Return a concise loading-condition assessment summary."""

    labels = {
        WBPlotStatus.WITHIN_LIMITS: "Within configured limits",
        WBPlotStatus.OUTSIDE_LIMITS: "Outside configured limits",
        WBPlotStatus.INCOMPLETE: "Assessment incomplete",
        WBPlotStatus.DEVELOPMENT: "Development assessment only",
    }

    return labels[loading.status]


def create_leg_cg_figure(leg: LegCGPlotResult):
    """Create an interactive CG figure with flight-leg details."""

    figure = create_cg_figure(leg.plot)

    origin = leg.departure_location_id or "Unknown"
    destination = leg.destination_location_id or "Unknown"

    figure.update_layout(
        title={
            "text": (
                f"Leg {leg.sequence_number}: {origin} → {destination}"
                "<br><sup>"
                f"Leg ID: {leg.leg_id} | "
                f"Aircraft: {leg.plot.aircraft_profile_id} | "
                f"Configuration Revision: "
                f"{leg.plot.configuration_revision_number}"
                "</sup>"
            ),
            "x": 0.5,
            "xanchor": "center",
        }
    )

    assessments = []

    if leg.plot.zero_fuel_assessment is not None:
        assessments.append(
            (
                "ZFW",
                leg.plot.zero_fuel_assessment,
            )
        )

    if leg.plot.loading_points:
        assessments.append(
            (
                "Departure",
                leg.plot.loading_points[0],
            )
        )

    if leg.plot.arrival_assessment is not None:
        assessments.append(
            (
                "Arrival",
                leg.plot.arrival_assessment,
            )
        )

    summary = " | ".join(
        f"{label}: {_assessment_summary(assessment)}"
        for label, assessment in assessments
    )

    figure.add_annotation(
        text=summary,
        xref="paper",
        yref="paper",
        x=0.5,
        y=1.09,
        xanchor="center",
        showarrow=False,
        font={"size": 11},
    )

    figure.update_layout(
        margin={"l": 70, "r": 40, "t": 150, "b": 100},
    )

    return figure


def export_leg_cg_html(
    leg: LegCGPlotResult,
    output_path: str | Path,
) -> Path:
    """Export a self-contained offline HTML CG graph."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    figure = create_leg_cg_figure(leg)

    figure.write_html(
        str(path),
        include_plotlyjs=True,
        full_html=True,
        auto_open=False,
    )

    return path
