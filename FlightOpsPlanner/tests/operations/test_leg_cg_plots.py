"""Tests for revision-bound per-leg CG plotting."""

from copy import deepcopy
from dataclasses import replace

import pytest

from flightops.operations.schemas.flight import FlightOperation
from flightops.operations.services.leg_cg_plots import (
    build_operation_cg_plots,
)
from flightops.operations.services.leg_weight_balance import (
    calculate_operation_weight_balance,
)
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
)
from flightops.weight_balance.plotting import (
    create_cg_figure,
)
from tests.operations.test_leg_weight_balance import make_leg
from tests.weight_balance.test_revision_bound_validation import aircraft
from tests.weight_balance.test_zero_fuel import configured_revision


def example_operation():
    """Create and calculate a fictional two-leg flight."""

    revision = configured_revision()
    aircraft_profile = aircraft()

    operation = FlightOperation(
        operation_id="FO-CG-001",
        aircraft_profile_id=aircraft_profile.id,
        configuration_revision_id=revision.id,
        legs=[
            make_leg(
                number=1,
                origin="HTZA",
                destination="HTDA",
                fuel_kg=60.0,
                burn_kg=20.0,
                baggage_kg=25.0,
            ),
            make_leg(
                number=2,
                origin="HTDA",
                destination="HTPE",
                fuel_kg=40.0,
                burn_kg=15.0,
                baggage_kg=0.0,
            ),
        ],
    )

    assessment = calculate_operation_weight_balance(
        operation,
        revision,
        aircraft_profile,
    )

    return assessment, revision, aircraft_profile


def test_operation_produces_one_graph_per_leg():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    assert len(result.legs) == 2
    assert result.legs[0].leg_id == "leg-1"
    assert result.legs[1].leg_id == "leg-2"


def test_each_graph_contains_three_loading_conditions():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    for leg in result.legs:
        assert len(leg.plot.loading_points) == 1
        assert leg.plot.zero_fuel_assessment is not None
        assert leg.plot.arrival_assessment is not None


def test_zfw_excludes_usable_fuel():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    first = result.legs[0].plot

    assert first.zero_fuel_point.weight_kg < first.loading_points[0].point.weight_kg


def test_arrival_weight_is_lower_than_departure():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    first = result.legs[0].plot

    assert (
        first.arrival_assessment.point.weight_kg
        < first.loading_points[0].point.weight_kg
    )


def test_passenger_or_baggage_changes_do_not_leak_between_legs():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    first = result.legs[0].plot
    second = result.legs[1].plot

    assert (
        first.zero_fuel_point.weight_kg - second.zero_fuel_point.weight_kg
    ) == pytest.approx(25.0)


def test_arrival_marker_is_blue():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    figure = create_cg_figure(result.legs[0].plot)

    arrival = next(trace for trace in figure.data if trace.name == "Arrival Weight")

    assert arrival.marker.color == "#0d6efd"


def test_zfw_marker_remains_red():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    figure = create_cg_figure(result.legs[0].plot)

    zfw = next(trace for trace in figure.data if trace.name == "Zero-Fuel Weight")

    assert zfw.marker.color == "#dc3545"


def test_fuel_burn_line_connects_departure_and_arrival():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    plot = result.legs[0].plot
    figure = create_cg_figure(plot)

    trend = next(
        trace
        for trace in figure.data
        if trace.name == "Planned fuel-burn endpoint trend"
    )

    assert trend.x == (
        plot.loading_points[0].point.cg_mm,
        plot.arrival_assessment.point.cg_mm,
    )

    assert trend.y == (
        plot.loading_points[0].point.weight_kg,
        plot.arrival_assessment.point.weight_kg,
    )


def test_graph_preserves_revision_identity():
    assessment, revision, aircraft_profile = example_operation()

    result = build_operation_cg_plots(
        assessment,
        revision,
        aircraft_profile,
    )

    for leg in result.legs:
        assert leg.plot.configuration_revision_id == revision.id
        assert leg.plot.configuration_revision_number == revision.revision_number


def test_wrong_aircraft_rejected():
    assessment, revision, aircraft_profile = example_operation()

    wrong_aircraft = deepcopy(aircraft_profile)
    wrong_aircraft.id = "incorrect-aircraft"

    with pytest.raises(ConfigurationAdapterError):
        build_operation_cg_plots(
            assessment,
            revision,
            wrong_aircraft,
        )


def test_wrong_revision_rejected():
    assessment, revision, aircraft_profile = example_operation()

    wrong_revision = deepcopy(revision)
    wrong_revision.id = "incorrect-revision"

    with pytest.raises(ConfigurationAdapterError):
        build_operation_cg_plots(
            assessment,
            wrong_revision,
            aircraft_profile,
        )


def test_tampered_loading_revision_rejected():
    assessment, revision, aircraft_profile = example_operation()

    first_leg = assessment.legs[0]

    bad_validation = replace(
        first_leg.arrival.validation,
        configuration_revision_id="incorrect-revision",
    )

    bad_arrival = replace(
        first_leg.arrival,
        validation=bad_validation,
    )

    bad_leg = replace(
        first_leg,
        arrival=bad_arrival,
    )

    bad_operation = replace(
        assessment,
        legs=(bad_leg, *assessment.legs[1:]),
    )

    with pytest.raises(ConfigurationAdapterError):
        build_operation_cg_plots(
            bad_operation,
            revision,
            aircraft_profile,
        )
