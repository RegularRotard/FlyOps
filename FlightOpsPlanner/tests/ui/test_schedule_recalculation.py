"""Regression tests for automatic flight schedule recalculation."""

from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]

HARNESS = ROOT / "tests" / "ui" / "flight_editor_harness.py"


def start_app():
    app = AppTest.from_file(
        str(HARNESS),
        default_timeout=20,
    ).run()

    assert not app.exception

    return app


def legs_from(app):
    return app.session_state["ui_test_result"]


def departure_time(leg):
    return datetime.fromisoformat(f"{leg['ETD Date']}T{leg['ETD Time']}")


def arrival_time(leg):
    return datetime.fromisoformat(str(leg["ETA"]))


def assert_schedule_valid(legs):
    """Every flight must depart no earlier than the previous arrival."""

    for index, leg in enumerate(legs):
        assert arrival_time(leg) > departure_time(leg)

        if index > 0:
            previous = legs[index - 1]

            assert departure_time(leg) >= arrival_time(previous), (
                f"{leg['Leg']} departs before {previous['Leg']} arrives."
            )


def click(app, label, index=0):
    buttons = [button for button in app.button if button.label == label]

    assert len(buttons) > index

    assert not buttons[index].disabled

    buttons[index].click().run()

    assert not app.exception

    return app


def test_initial_schedule_is_valid():
    app = start_app()

    assert_schedule_valid(legs_from(app))


def test_added_leg_respects_previous_arrival():
    app = start_app()

    click(app, "➕ Add Leg")

    legs = legs_from(app)

    assert len(legs) == 3

    assert_schedule_valid(legs)


def test_duplicate_respects_previous_arrival():
    app = start_app()

    click(app, "📋 Duplicate")

    legs = legs_from(app)

    assert len(legs) == 3

    assert_schedule_valid(legs)


def test_reorder_respects_previous_arrival():
    app = start_app()

    click(app, "⬇️ Down", 0)

    legs = legs_from(app)

    assert_schedule_valid(legs)


def test_scenic_duration_updates_eta():
    app = start_app()

    initial = legs_from(app)

    initial_eta = arrival_time(initial[0])

    click(app, "30 MIN")

    updated = legs_from(app)

    assert updated[0]["Flight Minutes"] == 30.0

    assert arrival_time(updated[0]) > initial_eta

    assert_schedule_valid(updated)


def test_duplicate_then_reorder_schedule():
    app = start_app()

    click(app, "📋 Duplicate")

    click(app, "⬇️ Down", 0)

    legs = legs_from(app)

    assert len(legs) == 3

    assert_schedule_valid(legs)


def test_route_continuity_after_reorder():
    app = start_app()

    click(app, "⬇️ Down", 0)

    legs = legs_from(app)

    for index in range(1, len(legs)):
        assert legs[index]["Departure"] == legs[index - 1]["Destination"]


def test_leg_numbering_remains_sequential():
    app = start_app()

    click(app, "📋 Duplicate")

    click(app, "⬇️ Down", 0)

    legs = legs_from(app)

    assert [leg["Leg"] for leg in legs] == [
        "LEG-001",
        "LEG-002",
        "LEG-003",
    ]
