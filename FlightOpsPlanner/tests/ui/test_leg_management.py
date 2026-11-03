"""Streamlit tests for adding, duplicating and reordering flight legs."""

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


def get_legs(app):
    return app.session_state["ui_test_result"]


def click_button(app, label, index=0):
    buttons = [button for button in app.button if button.label == label]

    assert len(buttons) > index, f"Button {label!r} was not found."

    buttons[index].click().run()

    assert not app.exception
    return app


def test_add_leg_from_summary():
    app = start_app()

    assert len(get_legs(app)) == 2

    click_button(app, "➕ Add Leg")

    legs = get_legs(app)

    assert len(legs) == 3
    assert legs[-1]["Leg"] == "LEG-003"


def test_duplicate_leg():
    app = start_app()

    click_button(app, "📋 Duplicate", 0)

    legs = get_legs(app)

    assert len(legs) == 3
    assert legs[1]["Flight Type"] == legs[0]["Flight Type"]
    assert legs[1]["Flight Minutes"] == legs[0]["Flight Minutes"]


def test_duplicate_preserves_route_continuity():
    app = start_app()

    click_button(app, "📋 Duplicate", 0)

    legs = get_legs(app)

    for index in range(1, len(legs)):
        assert legs[index]["Departure"] == legs[index - 1]["Destination"]


def test_move_leg_down():
    app = start_app()

    original_types = [leg["Flight Type"] for leg in get_legs(app)]

    click_button(app, "⬇️ Down", 0)

    updated_types = [leg["Flight Type"] for leg in get_legs(app)]

    assert updated_types == list(reversed(original_types))


def test_move_preserves_route_continuity():
    app = start_app()

    click_button(app, "⬇️ Down", 0)

    legs = get_legs(app)

    for index in range(1, len(legs)):
        assert legs[index]["Departure"] == legs[index - 1]["Destination"]


def test_leg_numbering_after_duplicate_and_move():
    app = start_app()

    click_button(app, "📋 Duplicate", 0)
    click_button(app, "⬇️ Down", 0)

    legs = get_legs(app)

    assert [leg["Leg"] for leg in legs] == [
        "LEG-001",
        "LEG-002",
        "LEG-003",
    ]


def test_reordering_boundary_buttons():
    """First leg cannot move up; last leg cannot move down."""

    app = start_app()

    up_buttons = [button for button in app.button if button.label == "⬆️ Up"]

    down_buttons = [button for button in app.button if button.label == "⬇️ Down"]

    assert len(up_buttons) == 2
    assert len(down_buttons) == 2

    assert up_buttons[0].disabled
    assert not up_buttons[1].disabled

    assert not down_buttons[0].disabled
    assert down_buttons[1].disabled
