"""Fast AG Grid entry for passengers, baggage and independent cargo."""

from dataclasses import replace
from uuid import uuid4

import pandas as pd
import streamlit as st

from app.manifest_grid import (
    build_manifest_rows,
    render_manifest_grid,
)
from app.manifest_grid_grouping import group_manifest_rows
from app.manifest_grid_service import (
    ManifestGridError,
    apply_grid_edits,
    clean_baggage_description,
    resolve_baggage_owner,
)
from app.manifest_live import (
    remove_baggage,
    remove_passenger,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)

PASSENGERS = "flyops_manifest_passengers"
BAGGAGE = "flyops_manifest_baggage"
ASSIGNMENTS = "flyops_manifest_assignments"
LOADING = "flyops_leg_station_assignments"

ASSIGNMENT_VERSION = "flyops_manifest_assignment_version"
LOADING_VERSION = "flyops_loading_widget_version"

DRAFTS = "flyops_grid_drafts"
SELECTED = "flyops_grid_selected_id"
GRID_VERSION = "flyops_grid_version"
FOCUS_RECORD = "flyops_grid_focus_record"

BAGGAGE_OVERRIDES = "flyops_baggage_leg_overrides"


def _initialise() -> None:
    state = st.session_state

    state.setdefault(PASSENGERS, {})
    state.setdefault(BAGGAGE, {})
    state.setdefault(ASSIGNMENTS, {})
    state.setdefault(LOADING, {})

    state.setdefault(DRAFTS, {})
    state.setdefault(SELECTED, None)
    state.setdefault(GRID_VERSION, 0)
    state.setdefault(FOCUS_RECORD, None)

    state.setdefault(ASSIGNMENT_VERSION, 0)
    state.setdefault(LOADING_VERSION, 0)


def _refresh_structure() -> None:
    """Force the grid to rebuild after adding or deleting records."""

    st.session_state[GRID_VERSION] += 1


def _refresh_assignment_widgets() -> None:
    """Prevent stale selectors from restoring deleted records."""

    state = st.session_state

    state[ASSIGNMENT_VERSION] += 1
    state[LOADING_VERSION] += 1


def _add_draft(record_type: str, owner_id: str | None = None) -> None:
    """Add an editable row without creating an invalid saved record."""

    record_id = uuid4().hex

    st.session_state[DRAFTS][record_id] = {
        "ID": record_id,
        "Type": record_type,
        "Description": "",
        "Weight (kg)": None,
        "Owner ID": owner_id or "",
    }

    st.session_state[SELECTED] = record_id
    st.session_state[FOCUS_RECORD] = record_id

    _refresh_structure()


def _selected_owner_id() -> str | None:
    """Resolve the baggage owner without an owner dropdown."""

    state = st.session_state

    return resolve_baggage_owner(
        state.get(SELECTED),
        state[PASSENGERS],
        state[BAGGAGE],
    )


def _add_passenger() -> None:
    _add_draft("Passenger")


def _add_bag() -> bool:
    """Create baggage for the active passenger."""

    owner_id = _selected_owner_id()

    if owner_id is None:
        st.error("Add a passenger before adding baggage.")
        return False

    _add_draft("Bag", owner_id)

    return True


def _add_cargo() -> None:
    _add_draft("Cargo")


def _clear_baggage_overrides(removed_ids: set[str]) -> None:
    """Remove deleted baggage from manual flight-leg routing exceptions."""

    overrides = st.session_state.get(BAGGAGE_OVERRIDES, {})

    for leg in overrides.values():
        for key in ("include", "exclude"):
            leg.setdefault(key, set()).difference_update(removed_ids)


def _delete_selected() -> None:
    """Delete the selected record and its dependent assignments."""

    state = st.session_state
    record_id = state[SELECTED]

    if not record_id:
        return

    if record_id in state[DRAFTS]:
        del state[DRAFTS][record_id]

    elif record_id in state[PASSENGERS]:
        before_baggage = set(state[BAGGAGE])

        (
            state[PASSENGERS],
            state[BAGGAGE],
            state[ASSIGNMENTS],
            state[LOADING],
        ) = remove_passenger(
            record_id,
            state[PASSENGERS],
            state[BAGGAGE],
            state[ASSIGNMENTS],
            state[LOADING],
        )

        deleted_baggage = before_baggage - set(state[BAGGAGE])

        _clear_baggage_overrides(deleted_baggage)

        # Any unsaved baggage drafts owned by this passenger
        # must also be removed.
        for draft_id, draft in list(state[DRAFTS].items()):
            if draft.get("Owner ID") == record_id:
                del state[DRAFTS][draft_id]

        _refresh_assignment_widgets()

    elif record_id in state[BAGGAGE]:
        (
            state[BAGGAGE],
            state[ASSIGNMENTS],
            state[LOADING],
        ) = remove_baggage(
            record_id,
            state[BAGGAGE],
            state[ASSIGNMENTS],
            state[LOADING],
            state[PASSENGERS],
        )

        _clear_baggage_overrides({record_id})
        _refresh_assignment_widgets()

    state[SELECTED] = None
    state[FOCUS_RECORD] = None
    _refresh_structure()


def _rows_with_drafts() -> pd.DataFrame:
    """Build a stable, passenger-centred manifest grid."""

    state = st.session_state

    saved_rows = build_manifest_rows(
        state[PASSENGERS],
        state[BAGGAGE],
    )

    draft_rows = [dict(row) for row in state[DRAFTS].values()]

    return group_manifest_rows(
        saved_rows,
        draft_rows,
    )


def _clean_existing_baggage() -> None:
    """Clean legacy display prefixes from saved session records."""

    state = st.session_state

    updated_baggage = dict(state[BAGGAGE])
    changed = False

    for baggage_id, item in updated_baggage.items():
        cleaned = clean_baggage_description(item.description)

        if cleaned != item.description:
            updated_baggage[baggage_id] = replace(
                item,
                description=cleaned,
            )
            changed = True

    if changed:
        state[BAGGAGE] = updated_baggage

        # Refresh the grid once so old frontend cell values
        # cannot overwrite the cleaned descriptions.
        state[GRID_VERSION] += 1


def _commit_grid_data(edited: pd.DataFrame) -> None:
    """Atomically apply completed cell edits to the session registers."""

    state = st.session_state

    existing_ids = set(state[PASSENGERS]) | set(state[BAGGAGE])

    existing_rows = edited[edited["ID"].isin(existing_ids)].copy()

    result = apply_grid_edits(
        existing_rows,
        state[PASSENGERS],
        state[BAGGAGE],
    )

    updated_passengers = dict(result.passengers)
    updated_baggage = dict(result.baggage)

    updated_drafts = dict(state[DRAFTS])

    # Rows created by AG Grid keyboard shortcuts are not
    # initially present in Streamlit Session State.
    # Register them as drafts before applying committed edits.
    for _, row in edited.iterrows():
        record_id = str(row["ID"])

        if record_id in existing_ids or record_id in updated_drafts:
            continue

        if not record_id.startswith("ui_"):
            raise ManifestGridError(f"Unexpected manifest record: {record_id}")

        record_type = str(row.get("Type", ""))

        if record_type not in (
            "Passenger",
            "Bag",
            "Cargo",
        ):
            raise ManifestGridError("Unknown manifest record type.")

        owner_id = row.get("Owner ID")

        if pd.isna(owner_id):
            owner_id = ""

        updated_drafts[record_id] = {
            "ID": record_id,
            "Type": record_type,
            "Description": "",
            "Weight (kg)": None,
            "Owner ID": str(owner_id or ""),
        }

    for _, row in edited.iterrows():
        record_id = str(row["ID"])

        if record_id not in updated_drafts:
            continue

        description = str(row.get("Description") or "").strip()

        draft = dict(updated_drafts[record_id])

        if draft["Type"] == "Bag":
            description = clean_baggage_description(description)

        draft["Description"] = description

        raw_weight = row.get("Weight (kg)")

        if pd.isna(raw_weight) or raw_weight == "":
            weight = None
        else:
            try:
                weight = float(raw_weight)
            except (ValueError, TypeError) as error:
                raise ManifestGridError("Weight must be numeric.") from error

            if not 0 <= weight < float("inf"):
                raise ManifestGridError("Weight must be finite and nonnegative.")

        draft["Weight (kg)"] = weight

        if not description:
            updated_drafts[record_id] = draft
            continue

        if draft["Type"] == "Passenger":
            updated_passengers[record_id] = Passenger(
                passenger_id=record_id,
                name=description,
                verified_weight=weight,
            )

        else:
            owner_id = draft["Owner ID"] or None

            if owner_id and owner_id not in updated_passengers:
                raise ManifestGridError("Baggage owner does not exist.")

            updated_baggage[record_id] = BaggageItem(
                baggage_id=record_id,
                description=description,
                owner_passenger_id=owner_id,
                verified_weight=weight,
            )

        del updated_drafts[record_id]

    # Only replace Session State after every row validates.
    state[PASSENGERS] = updated_passengers
    state[BAGGAGE] = updated_baggage
    state[DRAFTS] = updated_drafts


def _update_selection(grid_result) -> None:
    """Preserve an active record across grid edit reruns.

    Some AG Grid events return no selected rows even when
    an edit has just been committed. That must not erase
    the last valid selection.
    """

    selected = grid_result.selected_rows

    if selected is None:
        return

    if isinstance(selected, pd.DataFrame):
        if selected.empty:
            return

        record_id = selected.iloc[0].get("ID")

    elif isinstance(selected, list):
        if not selected:
            return

        record_id = selected[0].get("ID")

    else:
        return

    if record_id is None or pd.isna(record_id):
        return

    st.session_state[SELECTED] = str(record_id)


def render_grid_manifest_register() -> None:
    """Render the integrated, automatically saving manifest register."""

    _initialise()

    state = st.session_state

    st.markdown("### 👥 Passengers & Baggage")

    # Actions appear in one compact toolbar.
    add_pax, add_bag, add_cargo, delete = st.columns([1.2, 1.2, 1.2, 1.5])

    with add_pax:
        if st.button(
            "＋ Passenger",
            use_container_width=True,
        ):
            _add_passenger()
            st.rerun()

    with add_bag:
        owner_id = _selected_owner_id()

        owner_name = (
            state[PASSENGERS][owner_id].name if owner_id in state[PASSENGERS] else None
        )

        bag_label = f"＋ Bag → {owner_name}" if owner_name else "＋ Bag"

        if (
            st.button(
                bag_label,
                use_container_width=True,
                disabled=owner_id is None,
            )
            and _add_bag()
        ):
            st.rerun()

    with add_cargo:
        if st.button(
            "＋ Cargo",
            use_container_width=True,
        ):
            _add_cargo()
            st.rerun()

    with delete:
        if st.button(
            "🗑 Delete Selected",
            use_container_width=True,
            disabled=state[SELECTED] is None,
        ):
            _delete_selected()
            st.rerun()

    _clean_existing_baggage()

    st.caption(
        "Keyboard shortcuts (grid focused): "
        "Ctrl+Enter = passenger · "
        "Ctrl+Shift+B = bag · "
        "Ctrl+Shift+C = cargo · "
        "Tab = next field"
    )

    rows = _rows_with_drafts()

    grid_result = render_manifest_grid(
        rows,
        key=f"flyops_integrated_manifest_grid_{state[GRID_VERSION]}",
        focus_record_id=state[FOCUS_RECORD],
    )

    _update_selection(grid_result)

    edited = grid_result.data

    if edited is not None:
        edited = pd.DataFrame(edited)

        try:
            _commit_grid_data(edited)

        except (ManifestGridError, ValueError) as error:
            st.error(f"Manifest edit rejected: {error}")

    passenger_count = len(state[PASSENGERS])

    baggage_count = sum(
        item.owner_passenger_id is not None for item in state[BAGGAGE].values()
    )

    cargo_count = sum(
        item.owner_passenger_id is None for item in state[BAGGAGE].values()
    )

    known_weights = [
        record.effective_weight_kg
        for record in (
            *state[PASSENGERS].values(),
            *state[BAGGAGE].values(),
        )
        if record.effective_weight_kg is not None
    ]

    missing_count = sum(
        record.effective_weight_kg is None
        for record in (
            *state[PASSENGERS].values(),
            *state[BAGGAGE].values(),
        )
    )

    st.caption(
        f"{passenger_count} passengers  ·  "
        f"{baggage_count} bags  ·  "
        f"{cargo_count} cargo items  ·  "
        f"Known weight: {sum(known_weights):.1f} kg"
    )

    if missing_count:
        st.warning(
            f"{missing_count} record(s) have no weight. "
            "Their loads cannot be treated as complete."
        )
