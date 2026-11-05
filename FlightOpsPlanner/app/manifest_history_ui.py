"""Streamlit adapter for draft manifest undo history."""

import streamlit as st

from app.manifest_history import (
    ManifestHistory,
    capture_manifest_snapshot,
    snapshot_matches,
)

HISTORY_STATE = "flyops_manifest_undo_history"

PASSENGERS = "flyops_manifest_passengers"
BAGGAGE = "flyops_manifest_baggage"
ASSIGNMENTS = "flyops_manifest_assignments"

LOADING = "flyops_leg_station_assignments"
OVERRIDES = "flyops_baggage_leg_overrides"
DRAFTS = "flyops_grid_drafts"

GRID_VERSION = "flyops_grid_version"

ASSIGNMENT_VERSION = "flyops_manifest_assignment_version"
LOADING_VERSION = "flyops_loading_widget_version"

SELECTED = "flyops_grid_selected_id"
FOCUS_RECORD = "flyops_grid_focus_record"


def get_manifest_history() -> ManifestHistory:
    """Retrieve or create the current session's undo history."""

    return st.session_state.setdefault(
        HISTORY_STATE,
        ManifestHistory(),
    )


def capture_current_manifest():
    """Capture the current draft register and its assignments."""

    state = st.session_state

    return capture_manifest_snapshot(
        passengers=state.get(PASSENGERS, {}),
        baggage=state.get(BAGGAGE, {}),
        assignments=state.get(ASSIGNMENTS, {}),
        loading_assignments=state.get(LOADING, {}),
        baggage_overrides=state.get(OVERRIDES, {}),
        drafts=state.get(DRAFTS, {}),
    )


def record_manifest_change(
    description: str,
    before,
) -> bool:
    """Store an undo point only if tracked state actually changed."""

    state = st.session_state

    unchanged = snapshot_matches(
        before,
        passengers=state.get(PASSENGERS, {}),
        baggage=state.get(BAGGAGE, {}),
        assignments=state.get(ASSIGNMENTS, {}),
        loading_assignments=state.get(LOADING, {}),
        baggage_overrides=state.get(OVERRIDES, {}),
        drafts=state.get(DRAFTS, {}),
    )

    if unchanged:
        return False

    get_manifest_history().record(
        description,
        before,
    )

    return True


def undo_manifest_change() -> bool:
    """Restore one prior draft-manifest state."""

    state = st.session_state

    snapshot = get_manifest_history().undo()

    if snapshot is None:
        return False

    state[PASSENGERS] = snapshot.passengers
    state[BAGGAGE] = snapshot.baggage
    state[ASSIGNMENTS] = snapshot.assignments

    state[LOADING] = snapshot.loading_assignments
    state[OVERRIDES] = snapshot.baggage_overrides
    state[DRAFTS] = snapshot.drafts

    # Force a fresh AG Grid mount. Otherwise stale browser-side
    # rows could overwrite the restored Python state.
    state[GRID_VERSION] = (
        state.get(
            GRID_VERSION,
            0,
        )
        + 1
    )

    # Rebuild leg and loading widgets from restored assignments.
    state[ASSIGNMENT_VERSION] = (
        state.get(
            ASSIGNMENT_VERSION,
            0,
        )
        + 1
    )

    state[LOADING_VERSION] = (
        state.get(
            LOADING_VERSION,
            0,
        )
        + 1
    )

    state[SELECTED] = None
    state[FOCUS_RECORD] = None

    return True
