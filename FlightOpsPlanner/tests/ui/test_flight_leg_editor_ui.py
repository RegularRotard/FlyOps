"""Streamlit interface tests for the FlyOps flight-leg editor."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_APP = PROJECT_ROOT / "tests" / "ui" / "flight_editor_harness.py"


def start_editor():
    """Launch the isolated flight-leg editor."""

    return AppTest.from_file(
        str(TEST_APP),
        default_timeout=20,
    ).run()


def assert_no_exceptions(app):
    """Verify the Streamlit application executed successfully."""

    assert len(app.exception) == 0, [exception.message for exception in app.exception]


def test_editor_initial_render():
    """Editor should render two demonstration legs."""

    app = start_editor()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert len(legs) == 2
    assert legs[0]["Leg"] == "LEG-001"
    assert legs[1]["Leg"] == "LEG-002"


def test_editor_initial_routes():
    """The second departure must match the first destination."""

    app = start_editor()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert legs[0]["Departure"] == "HTZA"
    assert legs[0]["Destination"] == "HTZA"

    assert legs[1]["Departure"] == legs[0]["Destination"]


def test_scenic_return_location():
    """Scenic flights must return to their departure location."""

    app = start_editor()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert legs[0]["Flight Type"] == "Scenic"
    assert legs[0]["Departure"] == legs[0]["Destination"]


def test_eta_is_calculated_for_each_leg():
    """Each flight leg should have its own ETA."""

    app = start_editor()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert "ETD Date" in legs[0]
    assert "ETD Time" in legs[0]
    assert "ETA" in legs[0]

    assert "ETD Date" in legs[1]
    assert "ETD Time" in legs[1]
    assert "ETA" in legs[1]


def test_add_flight_leg():
    """Adding a leg should update the sequence automatically."""

    app = start_editor()

    assert_no_exceptions(app)

    add_button = next(
        button for button in app.button if button.label == "➕ Add Flight Leg"
    )

    add_button.click().run()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert len(legs) == 3
    assert [leg["Leg"] for leg in legs] == [
        "LEG-001",
        "LEG-002",
        "LEG-003",
    ]


def test_remove_flight_leg():
    """Removing a leg should renumber the remaining legs."""

    app = start_editor()

    assert_no_exceptions(app)

    remove_buttons = [button for button in app.button if "Remove" in button.label]

    assert len(remove_buttons) == 2

    remove_buttons[0].click().run()

    assert_no_exceptions(app)

    legs = app.session_state["ui_test_result"]

    assert len(legs) == 1
    assert legs[0]["Leg"] == "LEG-001"


def test_remove_all_flight_legs():
    """Removing every leg must not crash the interface."""

    app = start_editor()

    assert_no_exceptions(app)

    for _ in range(2):
        remove_button = next(
            button for button in app.button if "Remove" in button.label
        )

        remove_button.click().run()

        assert_no_exceptions(app)

    assert app.session_state["ui_test_result"] == []
