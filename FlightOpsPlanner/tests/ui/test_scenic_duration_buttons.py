"""Streamlit UI tests for Scenic duration buttons."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "ui" / "flight_editor_harness.py"


def start_app():
    app = AppTest.from_file(
        str(HARNESS),
        default_timeout=20,
    )
    app.run()
    assert not app.exception
    return app


def scenic_leg(app):
    return app.session_state["ui_test_result"][0]


def test_scenic_buttons_visible():
    app = start_app()

    labels = [button.label for button in app.button]

    assert "15 MIN" in labels
    assert "30 MIN" in labels


def test_initial_scenic_duration():
    app = start_app()

    assert scenic_leg(app)["Flight Type"] == "Scenic"
    assert scenic_leg(app)["Flight Minutes"] == 15.0


def test_select_thirty_minutes():
    app = start_app()

    button = next(item for item in app.button if item.label == "30 MIN")

    button.click().run()

    assert not app.exception
    assert scenic_leg(app)["Flight Minutes"] == 30.0


def test_switch_back_to_fifteen_minutes():
    app = start_app()

    next(item for item in app.button if item.label == "30 MIN").click().run()

    next(item for item in app.button if item.label == "15 MIN").click().run()

    assert not app.exception
    assert scenic_leg(app)["Flight Minutes"] == 15.0


def test_scenic_buttons_do_not_change_flight_type():
    app = start_app()

    next(item for item in app.button if item.label == "30 MIN").click().run()

    assert scenic_leg(app)["Flight Type"] == "Scenic"


def test_scenic_has_no_numeric_eti_widget():
    app = start_app()

    # The second demonstration leg remains a Charter.
    eti_widgets = [
        widget for widget in app.number_input if widget.label == "ETI (minutes)"
    ]

    assert len(eti_widgets) == 1
