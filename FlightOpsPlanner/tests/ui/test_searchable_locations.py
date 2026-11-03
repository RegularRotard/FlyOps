"""Verify flight-planning locations use searchable selectors."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "ui" / "flight_editor_harness.py"


def test_departure_and_destination_are_selectboxes():
    app = AppTest.from_file(
        str(HARNESS),
        default_timeout=20,
    ).run()

    assert not app.exception

    labels = [widget.label for widget in app.selectbox]

    assert any(label.startswith("Departure") for label in labels)

    assert any(label.startswith("Destination") for label in labels)

    text_labels = [widget.label for widget in app.text_input]

    assert "Departure" not in text_labels
    assert "Destination" not in text_labels


def test_location_selection_preserves_route_continuity():
    app = AppTest.from_file(
        str(HARNESS),
        default_timeout=20,
    ).run()

    assert not app.exception

    legs = app.session_state["ui_test_result"]

    assert legs[1]["Departure"] == legs[0]["Destination"]
