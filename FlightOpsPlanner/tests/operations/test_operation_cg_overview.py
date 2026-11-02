"""Tests for multi-leg CG overview rendering."""

from dataclasses import replace
from html.parser import HTMLParser

import pytest

from flightops.operations.services.leg_cg_plots import (
    build_operation_cg_plots,
)
from flightops.operations.services.operation_cg_overview import (
    create_operation_cg_overview,
    export_operation_cg_overview,
)
from tests.operations.test_leg_cg_plots import example_operation


def sample_overview():
    assessment, revision, aircraft = example_operation()

    return build_operation_cg_plots(
        assessment,
        revision,
        aircraft,
    )


def test_overview_contains_all_flight_legs():
    figure = create_operation_cg_overview(sample_overview())

    names = [trace.name for trace in figure.data]

    assert "Leg 1 ZFW" in names
    assert "Leg 1 Departure" in names
    assert "Leg 1 Arrival" in names

    assert "Leg 2 ZFW" in names
    assert "Leg 2 Departure" in names
    assert "Leg 2 Arrival" in names


def test_zfw_points_are_red():
    figure = create_operation_cg_overview(sample_overview())

    zfw_traces = [trace for trace in figure.data if trace.name.endswith(" ZFW")]

    assert len(zfw_traces) == 2

    assert all(trace.marker.color == "#dc3545" for trace in zfw_traces)


def test_arrival_points_are_blue():
    figure = create_operation_cg_overview(sample_overview())

    arrivals = [trace for trace in figure.data if trace.name.endswith(" Arrival")]

    assert len(arrivals) == 2

    assert all(trace.marker.color == "#0d6efd" for trace in arrivals)


def test_each_leg_has_independent_loading_points():
    overview = sample_overview()
    figure = create_operation_cg_overview(overview)

    departure_trace = next(
        trace for trace in figure.data if trace.name == "Leg 1 Departure"
    )

    assert departure_trace.x == (overview.legs[0].plot.loading_points[0].point.cg_mm,)

    assert departure_trace.y == (
        overview.legs[0].plot.loading_points[0].point.weight_kg,
    )


def test_overview_rejects_inconsistent_revision():
    overview = sample_overview()

    modified_plot = replace(
        overview.legs[1].plot,
        configuration_revision_id="incorrect-revision",
    )

    modified_leg = replace(
        overview.legs[1],
        plot=modified_plot,
    )

    modified_overview = replace(
        overview,
        legs=(overview.legs[0], modified_leg),
    )

    with pytest.raises(ValueError, match="inconsistent aircraft revisions"):
        create_operation_cg_overview(modified_overview)


def test_overview_rejects_missing_arrival():
    overview = sample_overview()

    modified_plot = replace(
        overview.legs[0].plot,
        arrival_assessment=None,
    )

    modified_leg = replace(
        overview.legs[0],
        plot=modified_plot,
    )

    modified_overview = replace(
        overview,
        legs=(modified_leg, *overview.legs[1:]),
    )

    with pytest.raises(ValueError, match="missing a loading assessment"):
        create_operation_cg_overview(modified_overview)


def test_export_is_self_contained_html(tmp_path):
    class ScriptInspector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.external_scripts = []

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                source = dict(attrs).get("src")
                if source:
                    self.external_scripts.append(source)

    output = tmp_path / "operation_cg_overview.html"

    returned = export_operation_cg_overview(
        sample_overview(),
        output,
    )

    assert returned == output
    assert output.exists()

    html = output.read_text(encoding="utf-8")

    inspector = ScriptInspector()
    inspector.feed(html)

    assert "Leg 1 Departure" in html
    assert "Leg 2 Arrival" in html
    assert "Plotly.newPlot" in html
    assert inspector.external_scripts == []


def test_empty_overview_rejected():
    overview = sample_overview()

    empty = replace(overview, legs=())

    with pytest.raises(ValueError, match="without flight legs"):
        create_operation_cg_overview(empty)
