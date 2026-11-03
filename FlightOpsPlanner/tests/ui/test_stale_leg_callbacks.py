"""Regression tests for obsolete Streamlit flight-leg callbacks."""

from unittest.mock import patch

import pytest

from app import flight_leg_editor


@pytest.mark.parametrize(
    "callback_name",
    [
        "_update_field",
        "_flight_type_changed",
        "_duration_changed",
    ],
)
def test_stale_leg_callback_does_not_crash(callback_name):
    callback = getattr(flight_leg_editor, callback_name)

    with patch.object(
        flight_leg_editor,
        "_find_leg",
        side_effect=ValueError("Unknown flight-leg editor ID: obsolete-leg"),
    ):
        if callback_name == "_update_field":
            callback("obsolete-leg", "Departure")
        else:
            callback("obsolete-leg")


@pytest.mark.parametrize(
    "callback_name",
    [
        "_update_field",
        "_flight_type_changed",
        "_duration_changed",
    ],
)
def test_unexpected_lookup_error_is_not_suppressed(callback_name):
    callback = getattr(flight_leg_editor, callback_name)

    with (
        patch.object(
            flight_leg_editor,
            "_find_leg",
            side_effect=ValueError("Unexpected configuration error"),
        ),
        pytest.raises(
            ValueError,
            match="Unexpected configuration error",
        ),
    ):
        if callback_name == "_update_field":
            callback("broken-leg", "Departure")
        else:
            callback("broken-leg")
