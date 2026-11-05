"""Compact passenger and baggage management for FlyOps."""

import streamlit as st

from app.baggage_sync import (
    derive_overrides,
    reconcile_baggage_overrides,
    synchronise_baggage,
)
from app.manifest_assignments import (
    build_leg_manifests,
    find_discontinuous_assignments,
    reconcile_assignments,
)
from app.manifest_grid_ui import render_grid_manifest_register
from app.manifest_tables import (
    apply_manifest_rows,
    baggage_rows,
    owner_options,
    passenger_rows,
)
from flightops.operations.manifests.service import (
    calculate_operation_loads,
)

PASSENGER_STATE = "flyops_manifest_passengers"
BAGGAGE_STATE = "flyops_manifest_baggage"
ASSIGNMENT_STATE = "flyops_manifest_assignments"
ORDER_STATE = "flyops_manifest_leg_order"
REVIEW_STATE = "flyops_manifest_review_legs"

TABLE_VERSION = "flyops_manifest_table_version"
BAGGAGE_OVERRIDE_STATE = "flyops_baggage_leg_overrides"
ASSIGNMENT_WIDGET_VERSION = "flyops_manifest_assignment_version"


def _initialise_state(legs: list[dict]) -> list[str]:
    """Initialise registers and preserve stable leg assignments."""

    state = st.session_state

    state.setdefault(PASSENGER_STATE, {})
    state.setdefault(BAGGAGE_STATE, {})
    state.setdefault(ASSIGNMENT_STATE, {})
    state.setdefault(REVIEW_STATE, set())
    state.setdefault(TABLE_VERSION, 0)
    state.setdefault(ASSIGNMENT_WIDGET_VERSION, 0)

    uids = [leg["_uid"] for leg in legs]

    previous_order = state.get(ORDER_STATE)

    if previous_order is not None:
        old_shared = [uid for uid in previous_order if uid in uids]

        new_shared = [uid for uid in uids if uid in previous_order]

        if old_shared != new_shared:
            for uid in uids:
                assignment = state[ASSIGNMENT_STATE].get(
                    uid,
                    {},
                )

                if assignment.get("passengers") or assignment.get("baggage"):
                    state[REVIEW_STATE].add(uid)

    state[ASSIGNMENT_STATE] = reconcile_assignments(
        state[ASSIGNMENT_STATE],
        uids,
        state[PASSENGER_STATE],
        state[BAGGAGE_STATE],
    )

    state[REVIEW_STATE].intersection_update(uids)
    state[ORDER_STATE] = uids

    if _synchronise_leg_baggage(uids):
        state[ASSIGNMENT_WIDGET_VERSION] = state.get(ASSIGNMENT_WIDGET_VERSION, 0) + 1

    return uids


def _synchronise_leg_baggage(uids: list[str]) -> bool:
    """Synchronise owned baggage while retaining manual exceptions."""

    state = st.session_state
    assignments = state[ASSIGNMENT_STATE]
    baggage = state[BAGGAGE_STATE]

    overrides = state.setdefault(
        BAGGAGE_OVERRIDE_STATE,
        {},
    )

    # Existing manually selected baggage becomes an explicit
    # exception where it differs from the automatic selection.
    for uid in uids:
        if uid not in overrides:
            leg = assignments[uid]

            overrides[uid] = derive_overrides(
                leg["passengers"],
                leg["baggage"],
                baggage,
            )

    overrides = reconcile_baggage_overrides(
        overrides,
        uids,
        set(baggage),
    )

    state[BAGGAGE_OVERRIDE_STATE] = overrides

    changed = False

    for uid in uids:
        leg = assignments[uid]

        expected = synchronise_baggage(
            leg["passengers"],
            baggage,
            overrides[uid],
        )

        if leg["baggage"] != expected:
            leg["baggage"] = expected
            changed = True

    return changed


def _reset_assignment_widgets(uids: list[str]) -> None:
    """Refresh selectors after register records are changed."""

    for uid in uids:
        st.session_state.pop(
            f"manifest_leg_passengers_{uid}",
            None,
        )

        st.session_state.pop(
            f"manifest_leg_baggage_{uid}",
            None,
        )


def _render_registers(uids: list[str]) -> None:
    """Render both editable registers in one compact form."""

    passengers = st.session_state[PASSENGER_STATE]
    baggage = st.session_state[BAGGAGE_STATE]

    labels = owner_options(passengers)

    version = st.session_state[TABLE_VERSION]

    with st.form(
        "flyops_compact_manifest_registers",
        border=False,
    ):
        st.markdown("**Passengers**")

        edited_passengers = st.data_editor(
            passenger_rows(passengers),
            key=f"manifest_passenger_table_{version}",
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "ID": None,
                "Name": st.column_config.TextColumn(
                    "Passenger",
                    required=True,
                    width="large",
                ),
                "Weight (kg)": (
                    st.column_config.NumberColumn(
                        "Weight (kg)",
                        min_value=0.0,
                        step=0.5,
                        format="%.1f",
                        width="small",
                    )
                ),
            },
            disabled=["ID"],
        )

        st.markdown("**Baggage**")

        edited_baggage = st.data_editor(
            baggage_rows(baggage, passengers),
            key=f"manifest_baggage_table_{version}",
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "ID": None,
                "Description": (
                    st.column_config.TextColumn(
                        "Description",
                        required=True,
                        width="large",
                    )
                ),
                "Owner": st.column_config.SelectboxColumn(
                    "Owner",
                    options=list(labels),
                    default="Unaccompanied",
                    width="medium",
                ),
                "Weight (kg)": (
                    st.column_config.NumberColumn(
                        "Weight (kg)",
                        min_value=0.0,
                        step=0.5,
                        format="%.1f",
                        width="small",
                    )
                ),
            },
            disabled=["ID"],
        )

        applied = st.form_submit_button(
            "Apply Changes",
            type="primary",
            use_container_width=True,
        )

    if not applied:
        return

    try:
        new_passengers, new_baggage = apply_manifest_rows(
            edited_passengers,
            edited_baggage,
            passengers,
            baggage,
            labels,
        )

    except (TypeError, ValueError) as error:
        st.error(str(error))
        return

    # Identify deleted records before replacing the registers.
    deleted_passenger_ids = set(passengers) - set(new_passengers)
    deleted_baggage_ids = set(baggage) - set(new_baggage)

    # Remove deleted passengers and baggage from aircraft
    # loading-station assignments on every flight leg.
    loading_assignments = st.session_state.get(
        "flyops_leg_station_assignments",
        {},
    )

    for leg_loading in loading_assignments.values():
        for passenger_id in deleted_passenger_ids:
            leg_loading.get("passengers", {}).pop(
                passenger_id,
                None,
            )

        for baggage_id in deleted_baggage_ids:
            leg_loading.get("baggage", {}).pop(
                baggage_id,
                None,
            )

    # Rebuild station selectors so stale widget state
    # cannot restore a deleted passenger or baggage item.
    if deleted_passenger_ids or deleted_baggage_ids:
        st.session_state["flyops_loading_widget_version"] = (
            st.session_state.get(
                "flyops_loading_widget_version",
                0,
            )
            + 1
        )

    # Both registers are validated before either is changed.
    st.session_state[PASSENGER_STATE] = new_passengers
    st.session_state[BAGGAGE_STATE] = new_baggage

    st.session_state[ASSIGNMENT_STATE] = reconcile_assignments(
        st.session_state[ASSIGNMENT_STATE],
        uids,
        new_passengers,
        new_baggage,
    )

    # Force selectors to rebuild from reconciled assignments.
    # Reusing their previous widget keys can restore deleted IDs.
    st.session_state[ASSIGNMENT_WIDGET_VERSION] += 1
    st.session_state[TABLE_VERSION] += 1

    st.rerun()


def _save_leg_assignment(
    uid: str,
    record_type: str,
) -> None:
    """Save a leg selection and its baggage routing exceptions."""

    state = st.session_state

    version = state[ASSIGNMENT_WIDGET_VERSION]

    if record_type == "passengers":
        key = f"manifest_leg_passengers_{uid}_{version}"
    elif record_type == "baggage":
        key = f"manifest_leg_baggage_{uid}_{version}"
    else:
        raise ValueError("Unknown assignment type.")

    assignment = state[ASSIGNMENT_STATE].get(uid)

    if assignment is None:
        return

    selected = set(state[key])

    if record_type == "passengers":
        assignment["passengers"] = selected

        # Keep manual baggage exceptions, but automatically
        # update the baggage following the selected passengers.
        overrides = state.setdefault(
            BAGGAGE_OVERRIDE_STATE,
            {},
        )

        overrides.setdefault(
            uid,
            {"include": set(), "exclude": set()},
        )

        assignment["baggage"] = synchronise_baggage(
            selected,
            state[BAGGAGE_STATE],
            overrides[uid],
        )

        # Refresh baggage multiselect defaults after a
        # passenger selection changes.
        state[ASSIGNMENT_WIDGET_VERSION] += 1

    else:
        assignment["baggage"] = selected

        state.setdefault(
            BAGGAGE_OVERRIDE_STATE,
            {},
        )[uid] = derive_overrides(
            assignment["passengers"],
            selected,
            state[BAGGAGE_STATE],
        )

    state[REVIEW_STATE].discard(uid)


def _render_leg_assignments(
    legs: list[dict],
    uids: list[str],
) -> None:
    """Render compact, directly editable per-leg manifests."""

    passengers = st.session_state[PASSENGER_STATE]
    baggage = st.session_state[BAGGAGE_STATE]
    assignments = st.session_state[ASSIGNMENT_STATE]

    if not legs:
        st.info("Add a flight leg to assign passengers.")
        return

    manifests = build_leg_manifests(assignments, uids)

    loads = calculate_operation_loads(
        manifests,
        passengers,
        baggage,
    )

    st.markdown("**Flight Leg Assignments**")

    heading = st.columns([1, 2.5, 2.5, 1.2])

    heading[0].caption("LEG")
    heading[1].caption("PASSENGERS")
    heading[2].caption("BAGGAGE")
    heading[3].caption("LOAD")

    for index, leg in enumerate(legs, start=1):
        uid = leg["_uid"]

        # Calculate again after widget callbacks have applied.
        assignment = assignments[uid]
        load = loads[uid]

        columns = st.columns(
            [1, 2.5, 2.5, 1.2],
            vertical_alignment="center",
        )

        with columns[0]:
            st.markdown(f"**{index:03d}**")
            st.caption(leg.get("Flight Type", ""))

        with columns[1]:
            st.multiselect(
                f"Passengers LEG-{index:03d}",
                options=list(passengers),
                default=sorted(assignment["passengers"]),
                format_func=lambda pid: passengers[pid].name,
                key=(
                    f"manifest_leg_passengers_{uid}_"
                    f"{st.session_state[ASSIGNMENT_WIDGET_VERSION]}"
                ),
                on_change=_save_leg_assignment,
                args=(uid, "passengers"),
                label_visibility="collapsed",
                placeholder="Select passengers",
            )

        with columns[2]:
            st.multiselect(
                f"Baggage LEG-{index:03d}",
                options=list(baggage),
                default=sorted(assignment["baggage"]),
                format_func=lambda bid: baggage[bid].description,
                key=(
                    f"manifest_leg_baggage_{uid}_"
                    f"{st.session_state[ASSIGNMENT_WIDGET_VERSION]}"
                ),
                on_change=_save_leg_assignment,
                args=(uid, "baggage"),
                label_visibility="collapsed",
                placeholder="Select baggage",
            )

        with columns[3]:
            st.markdown(f"**{load.total_weight_kg:.1f} kg**")

        if uid in st.session_state[REVIEW_STATE]:
            st.warning(
                f"LEG-{index:03d}: Flight order changed. Review onboard assignments."
            )

        for warning in load.warnings:
            st.caption(f"⚠️ LEG-{index:03d}: {warning}")

    discontinuous_passengers = find_discontinuous_assignments(
        assignments,
        uids,
        "passengers",
    )

    discontinuous_baggage = find_discontinuous_assignments(
        assignments,
        uids,
        "baggage",
    )

    if discontinuous_passengers:
        names = [passengers[pid].name for pid in sorted(discontinuous_passengers)]

        st.warning("Passengers assigned to nonconsecutive legs: " + ", ".join(names))

    if discontinuous_baggage:
        descriptions = [
            baggage[bid].description for bid in sorted(discontinuous_baggage)
        ]

        st.warning(
            "Baggage assigned to nonconsecutive legs: " + ", ".join(descriptions)
        )


def render_manifest_ui(legs: list[dict]) -> None:
    """Render the compact passenger and baggage workspace."""

    uids = _initialise_state(legs)

    st.divider()

    st.subheader("👥 Passengers & Baggage")

    st.caption(
        "Enter names and weights directly in the tables. "
        "Use Tab to move between cells. "
        "Register changes are applied together."
    )

    render_grid_manifest_register()

    st.divider()

    _render_leg_assignments(legs, uids)

    st.caption(
        "Loads exclude aircraft empty weight, fuel and "
        "aircraft-specific loading stations. "
        "Manifest data is not yet saved to the operations database."
    )
