"""Tests for per-leg CG graph presentation and offline export."""

from flightops.operations.services.leg_cg_export import (
    create_leg_cg_figure,
    export_leg_cg_html,
)
from flightops.operations.services.leg_cg_plots import (
    build_operation_cg_plots,
)
from tests.operations.test_leg_cg_plots import example_operation


def sample_leg():
    assessment, revision, aircraft = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft,
    )

    return result.legs[0]


def test_graph_title_contains_route():
    figure = create_leg_cg_figure(sample_leg())

    assert "HTZA" in figure.layout.title.text
    assert "HTDA" in figure.layout.title.text


def test_graph_title_contains_leg_number():
    figure = create_leg_cg_figure(sample_leg())

    assert "Leg 1" in figure.layout.title.text


def test_graph_title_contains_revision():
    leg = sample_leg()
    figure = create_leg_cg_figure(leg)

    assert (
        f"Configuration Revision: {leg.plot.configuration_revision_number}"
        in figure.layout.title.text
    )


def test_graph_contains_assessment_summary():
    figure = create_leg_cg_figure(sample_leg())

    annotations = [annotation.text for annotation in figure.layout.annotations]

    assert any("ZFW:" in text for text in annotations)
    assert any("Departure:" in text for text in annotations)
    assert any("Arrival:" in text for text in annotations)


def test_offline_graph_export(tmp_path):
    leg = sample_leg()

    output = tmp_path / "leg_1_cg.html"

    returned = export_leg_cg_html(
        leg,
        output,
    )

    assert returned == output
    assert output.exists()

    html = output.read_text(encoding="utf-8")

    assert "HTZA" in html
    assert "HTDA" in html
    assert "Zero-Fuel Weight" in html
    assert "Arrival Weight" in html
