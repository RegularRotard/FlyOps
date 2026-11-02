"""Tests for interactive CG envelope rendering."""

from dataclasses import replace
from types import SimpleNamespace

from flightops.aircraft.schemas.configuration import (
    CGEnvelopePoint,
    LongitudinalCGEnvelope,
)
from flightops.weight_balance.plot_data import (
    CGPlotPoint,
    WBPlotStatus,
    build_cg_plot_data,
)
from flightops.weight_balance.plotting import (
    create_cg_figure,
    export_cg_html,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    WBVerificationLevel,
)
from flightops.weight_balance.validation import WBValidationStatus


def sample_plot_data(
    *,
    status=WBValidationStatus.PASS,
    verification=WBVerificationLevel.VERIFIED,
    include_envelope=True,
):
    validation = SimpleNamespace(
        aircraft_profile_id="aircraft-001",
        configuration_revision_id="revision-003",
        configuration_revision_number=3,
        status=status,
        total_weight_kg=900.0,
        cg_mm=2500.0,
        weight_margin_kg=200.0,
        cg_evaluation=SimpleNamespace(
            forward_margin_mm=250.0,
            aft_margin_mm=150.0,
        ),
        findings=(),
    )

    assessment = RevisionBoundWBResult(
        calculation=SimpleNamespace(),
        validation=validation,
        verification_level=verification,
    )

    envelope = None

    if include_envelope:
        envelope = LongitudinalCGEnvelope(
            points=[
                CGEnvelopePoint(
                    weight_kg=700,
                    forward_limit_mm=2200,
                    aft_limit_mm=2700,
                ),
                CGEnvelopePoint(
                    weight_kg=1100,
                    forward_limit_mm=2300,
                    aft_limit_mm=2600,
                ),
            ]
        )

    return build_cg_plot_data(
        assessment,
        envelope,
        label="Takeoff",
    )


def test_figure_contains_envelope_and_loading_point():
    figure = create_cg_figure(sample_plot_data())

    assert len(figure.data) == 4


def test_loading_point_uses_validated_coordinates():
    figure = create_cg_figure(sample_plot_data())

    loading = figure.data[-1]

    assert loading.x == (2500.0,)
    assert loading.y == (900.0,)


def test_forward_boundary_uses_configured_limits():
    figure = create_cg_figure(sample_plot_data())

    forward = figure.data[1]

    assert forward.x == (2200, 2300)
    assert forward.y == (700, 1100)


def test_aft_boundary_uses_configured_limits():
    figure = create_cg_figure(sample_plot_data())

    aft = figure.data[2]

    assert aft.x == (2700, 2600)
    assert aft.y == (700, 1100)


def test_failed_assessment_uses_failure_colour():
    figure = create_cg_figure(sample_plot_data(status=WBValidationStatus.FAIL))

    assert figure.data[-1].marker.color == "#dc3545"


def test_incomplete_assessment_uses_warning_colour():
    figure = create_cg_figure(sample_plot_data(status=WBValidationStatus.INCOMPLETE))

    assert figure.data[-1].marker.color == "#ffc107"


def test_development_assessment_uses_distinct_colour():
    figure = create_cg_figure(
        sample_plot_data(verification=WBVerificationLevel.DEVELOPMENT)
    )

    assert figure.data[-1].marker.color == "#6f42c1"


def test_missing_envelope_does_not_prevent_plotting():
    figure = create_cg_figure(
        sample_plot_data(
            status=WBValidationStatus.INCOMPLETE,
            include_envelope=False,
        )
    )

    assert len(figure.data) == 1


def test_figure_contains_revision_number():
    figure = create_cg_figure(sample_plot_data())

    assert "Revision: 3" in figure.layout.title.text


def test_export_creates_offline_html(tmp_path):
    """Standalone HTML embeds Plotly without external script dependencies."""

    from html.parser import HTMLParser

    class ScriptInspector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.external_scripts = []
            self.inline_scripts = []

        def handle_starttag(self, tag, attrs):
            if tag != "script":
                return

            attributes = dict(attrs)
            source = attributes.get("src")

            if source:
                self.external_scripts.append(source)

        def handle_data(self, data):
            if data.strip():
                self.inline_scripts.append(data)

    output = tmp_path / "cg_envelope.html"

    returned = export_cg_html(
        sample_plot_data(),
        output,
    )

    assert returned == output
    assert output.exists()

    html = output.read_text(encoding="utf-8")

    inspector = ScriptInspector()
    inspector.feed(html)

    assert "Takeoff" in html
    assert "Plotly.newPlot" in html

    # The document must not load JavaScript from an external URL.
    assert inspector.external_scripts == []

    # Plotly JavaScript must be embedded in the document.
    assert any("Plotly" in script for script in inspector.inline_scripts)


def test_plot_status_values_are_distinct():
    assert len(set(WBPlotStatus)) == 4


def test_zero_fuel_point_is_red():
    plot = replace(
        sample_plot_data(),
        zero_fuel_point=CGPlotPoint(
            cg_mm=2480,
            weight_kg=800,
        ),
    )

    figure = create_cg_figure(plot)

    zfw = next(trace for trace in figure.data if trace.name == "Zero-Fuel Weight")

    assert zfw.marker.color == "#dc3545"
    assert zfw.x == (2480,)
    assert zfw.y == (800,)


def test_fuel_loading_trend_connects_zfw_to_takeoff():
    plot = replace(
        sample_plot_data(),
        zero_fuel_point=CGPlotPoint(
            cg_mm=2480,
            weight_kg=800,
        ),
    )

    figure = create_cg_figure(plot)

    trend = next(trace for trace in figure.data if trace.name == "Fuel loading trend")

    assert trend.x == (2480, 2500)
    assert trend.y == (800, 900)


def test_existing_graph_without_zfw_remains_unchanged():
    figure = create_cg_figure(sample_plot_data())

    assert len(figure.data) == 4
    assert all(trace.name != "Zero-Fuel Weight" for trace in figure.data)


def test_zfw_hover_displays_independent_failure():
    plot = sample_plot_data()

    zfw = CGPlotPoint(
        cg_mm=2480,
        weight_kg=800,
    )

    from flightops.weight_balance.plot_data import CGPlotLoadingPoint

    zfw_assessment = CGPlotLoadingPoint(
        label="Zero-Fuel Weight",
        point=zfw,
        status=WBPlotStatus.OUTSIDE_LIMITS,
        weight_margin_kg=200.0,
        forward_margin_mm=-20.0,
        aft_margin_mm=300.0,
        findings=("Forward CG limit exceeded.",),
    )

    plot = replace(
        plot,
        zero_fuel_point=zfw,
        zero_fuel_assessment=zfw_assessment,
    )

    figure = create_cg_figure(plot)

    zfw_trace = next(trace for trace in figure.data if trace.name == "Zero-Fuel Weight")

    assert zfw_trace.marker.color == "#dc3545"
    assert "Outside configured limits" in zfw_trace.hovertemplate
    assert "Forward CG limit exceeded." in zfw_trace.hovertemplate


def test_zfw_hover_displays_independent_pass():
    plot = sample_plot_data()

    zfw = CGPlotPoint(
        cg_mm=2480,
        weight_kg=800,
    )

    from flightops.weight_balance.plot_data import CGPlotLoadingPoint

    zfw_assessment = CGPlotLoadingPoint(
        label="Zero-Fuel Weight",
        point=zfw,
        status=WBPlotStatus.WITHIN_LIMITS,
        weight_margin_kg=300.0,
        forward_margin_mm=180.0,
        aft_margin_mm=120.0,
        findings=(),
    )

    plot = replace(
        plot,
        zero_fuel_point=zfw,
        zero_fuel_assessment=zfw_assessment,
    )

    figure = create_cg_figure(plot)

    zfw_trace = next(trace for trace in figure.data if trace.name == "Zero-Fuel Weight")

    assert zfw_trace.marker.color == "#dc3545"
    assert "Within configured limits" in zfw_trace.hovertemplate


def test_zfw_mismatched_coordinates_rejected():
    plot = sample_plot_data()

    from flightops.weight_balance.plot_data import CGPlotLoadingPoint

    plot = replace(
        plot,
        zero_fuel_point=CGPlotPoint(
            cg_mm=2480,
            weight_kg=800,
        ),
        zero_fuel_assessment=CGPlotLoadingPoint(
            label="Zero-Fuel Weight",
            point=CGPlotPoint(
                cg_mm=2500,
                weight_kg=800,
            ),
            status=WBPlotStatus.WITHIN_LIMITS,
            weight_margin_kg=None,
            forward_margin_mm=None,
            aft_margin_mm=None,
            findings=(),
        ),
    )

    import pytest

    with pytest.raises(ValueError, match="do not match"):
        create_cg_figure(plot)
