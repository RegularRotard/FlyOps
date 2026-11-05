"""Compact, autosaving passenger and baggage entry."""

from uuid import uuid4

import streamlit as st

from app.manifest_live import (
    remove_baggage,
    remove_passenger,
    update_baggage,
    update_passenger,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)

PASSENGER_STATE = "flyops_manifest_passengers"
BAGGAGE_STATE = "flyops_manifest_baggage"
ASSIGNMENT_STATE = "flyops_manifest_assignments"

LOADING_STATE = "flyops_leg_station_assignments"

ASSIGNMENT_VERSION = "flyops_manifest_assignment_version"
LOADING_VERSION = "flyops_loading_widget_version"

DRAFT_PASSENGERS = "flyops_draft_passengers"
DRAFT_BAGGAGE = "flyops_draft_baggage"


def _initialise():
    state = st.session_state

    state.setdefault(PASSENGER_STATE, {})
    state.setdefault(BAGGAGE_STATE, {})
    state.setdefault(ASSIGNMENT_STATE, {})
    state.setdefault(LOADING_STATE, {})

    state.setdefault(ASSIGNMENT_VERSION, 0)
    state.setdefault(LOADING_VERSION, 0)

    state.setdefault(DRAFT_PASSENGERS, {})
    state.setdefault(DRAFT_BAGGAGE, {})


def _refresh_assignments():
    """Invalidate selectors after record deletion."""

    state = st.session_state

    state[ASSIGNMENT_VERSION] += 1
    state[LOADING_VERSION] += 1


def _add_passenger():
    """Create an empty editable passenger row."""

    passenger_id = uuid4().hex

    st.session_state[DRAFT_PASSENGERS][passenger_id] = True


def _add_baggage(owner_id=None):
    """Create an empty baggage row for a passenger or cargo."""

    baggage_id = uuid4().hex

    st.session_state[DRAFT_BAGGAGE][baggage_id] = owner_id


def _commit_passenger(passenger_id):
    """Save a passenger after a field is committed."""

    state = st.session_state

    name = state.get(
        f"live_passenger_name_{passenger_id}",
        "",
    ).strip()

    weight = state.get(
        f"live_passenger_weight_{passenger_id}",
    )

    existing = state[PASSENGER_STATE].get(passenger_id)

    if not name:
        if existing is not None:
            st.toast("Passenger name cannot be empty.")
            state[f"live_passenger_name_{passenger_id}"] = existing.name

        return

    if existing is None:
        passenger = Passenger(
            passenger_id=passenger_id,
            name=name,
            verified_weight=weight,
        )
    else:
        passenger = update_passenger(
            existing,
            name=name,
            weight_kg=weight,
        )

    state[PASSENGER_STATE][passenger_id] = passenger
    state[DRAFT_PASSENGERS].pop(passenger_id, None)


def _commit_baggage(baggage_id):
    """Save a baggage item after a field is committed."""

    state = st.session_state

    description = state.get(
        f"live_baggage_description_{baggage_id}",
        "",
    ).strip()

    weight = state.get(
        f"live_baggage_weight_{baggage_id}",
    )

    existing = state[BAGGAGE_STATE].get(baggage_id)

    if not description:
        if existing is not None:
            st.toast("Baggage description cannot be empty.")

            state[f"live_baggage_description_{baggage_id}"] = existing.description

        return

    if existing is None:
        owner_id = state[DRAFT_BAGGAGE].get(baggage_id)

        item = BaggageItem(
            baggage_id=baggage_id,
            description=description,
            owner_passenger_id=owner_id,
            verified_weight=weight,
        )

    else:
        item = update_baggage(
            existing,
            description=description,
            weight_kg=weight,
        )

    state[BAGGAGE_STATE][baggage_id] = item
    state[DRAFT_BAGGAGE].pop(baggage_id, None)


def _delete_passenger(passenger_id):
    """Cascade passenger deletion through the complete draft."""

    state = st.session_state

    state[DRAFT_PASSENGERS].pop(
        passenger_id,
        None,
    )

    # Remove any incomplete baggage rows owned by this passenger.
    for baggage_id, owner_id in list(state[DRAFT_BAGGAGE].items()):
        if owner_id == passenger_id:
            del state[DRAFT_BAGGAGE][baggage_id]

    (
        state[PASSENGER_STATE],
        state[BAGGAGE_STATE],
        state[ASSIGNMENT_STATE],
        state[LOADING_STATE],
    ) = remove_passenger(
        passenger_id,
        state[PASSENGER_STATE],
        state[BAGGAGE_STATE],
        state[ASSIGNMENT_STATE],
        state[LOADING_STATE],
    )

    _refresh_assignments()


def _delete_baggage(baggage_id):
    """Delete baggage from the register and all flight legs."""

    state = st.session_state

    state[DRAFT_BAGGAGE].pop(
        baggage_id,
        None,
    )

    (
        state[BAGGAGE_STATE],
        state[ASSIGNMENT_STATE],
        state[LOADING_STATE],
    ) = remove_baggage(
        baggage_id,
        state[BAGGAGE_STATE],
        state[ASSIGNMENT_STATE],
        state[LOADING_STATE],
        state[PASSENGER_STATE],
    )

    _refresh_assignments()


def _passenger_row(passenger_id):
    """Render one keyboard-friendly passenger row."""

    state = st.session_state

    passenger = state[PASSENGER_STATE].get(passenger_id)

    name = passenger.name if passenger else ""

    weight = passenger.effective_weight_kg if passenger else None

    columns = st.columns(
        [4, 1.5, 1.2],
        vertical_alignment="center",
    )

    with columns[0]:
        st.text_input(
            "Passenger",
            value=name,
            key=f"live_passenger_name_{passenger_id}",
            on_change=_commit_passenger,
            args=(passenger_id,),
            label_visibility="collapsed",
            placeholder="Passenger name",
        )

    with columns[1]:
        st.number_input(
            "Weight (kg)",
            min_value=0.0,
            value=weight,
            step=0.5,
            format="%.1f",
            key=f"live_passenger_weight_{passenger_id}",
            on_change=_commit_passenger,
            args=(passenger_id,),
            label_visibility="collapsed",
            placeholder="kg",
        )

    with columns[2]:
        if st.button(
            "🗑 Delete",
            key=f"delete_passenger_{passenger_id}",
            use_container_width=True,
        ):
            _delete_passenger(passenger_id)
            st.rerun()


def _baggage_row(baggage_id):
    """Render one autosaving baggage row."""

    state = st.session_state

    item = state[BAGGAGE_STATE].get(baggage_id)

    description = item.description if item else ""

    weight = item.effective_weight_kg if item else None

    columns = st.columns(
        [4, 1.5, 1.2],
        vertical_alignment="center",
    )

    with columns[0]:
        st.text_input(
            "Baggage description",
            value=description,
            key=f"live_baggage_description_{baggage_id}",
            on_change=_commit_baggage,
            args=(baggage_id,),
            label_visibility="collapsed",
            placeholder="↳ Bag / cargo description",
        )

    with columns[1]:
        st.number_input(
            "Weight (kg)",
            min_value=0.0,
            value=weight,
            step=0.5,
            format="%.1f",
            key=f"live_baggage_weight_{baggage_id}",
            on_change=_commit_baggage,
            args=(baggage_id,),
            label_visibility="collapsed",
            placeholder="kg",
        )

    with columns[2]:
        if st.button(
            "🗑 Delete",
            key=f"delete_baggage_{baggage_id}",
            use_container_width=True,
        ):
            _delete_baggage(baggage_id)
            st.rerun()


def _baggage_ids_for_owner(owner_id):
    """Return saved and draft baggage belonging to an owner."""

    state = st.session_state

    saved = [
        baggage_id
        for baggage_id, item in state[BAGGAGE_STATE].items()
        if item.owner_passenger_id == owner_id
    ]

    drafts = [
        baggage_id
        for baggage_id, draft_owner in state[DRAFT_BAGGAGE].items()
        if draft_owner == owner_id
    ]

    return saved + drafts


def render_live_manifest_register():
    """Render integrated passenger and baggage entry."""

    _initialise()

    state = st.session_state

    st.markdown("### 👥 Passengers & Baggage")

    st.caption(
        "Changes save when you finish a field. Press Tab to move between fields."
    )

    headings = st.columns([4, 1.5, 1.2])

    headings[0].caption("PASSENGER / BAGGAGE")
    headings[1].caption("WEIGHT (KG)")
    headings[2].caption("ACTION")

    passenger_ids = list(state[PASSENGER_STATE])

    passenger_ids.extend(state[DRAFT_PASSENGERS])

    for passenger_id in passenger_ids:
        _passenger_row(passenger_id)

        for baggage_id in _baggage_ids_for_owner(passenger_id):
            _baggage_row(baggage_id)

        # Only a completed passenger can own saved baggage.
        if passenger_id in state[PASSENGER_STATE] and st.button(
            "＋ Add bag",
            key=f"add_bag_{passenger_id}",
        ):
            _add_baggage(passenger_id)
            st.rerun()

        st.divider()

    if st.button(
        "＋ Add passenger",
        type="primary",
    ):
        _add_passenger()
        st.rerun()

    st.markdown("#### Unaccompanied Baggage / Cargo")

    for baggage_id in _baggage_ids_for_owner(None):
        _baggage_row(baggage_id)

    if st.button(
        "＋ Add cargo",
    ):
        _add_baggage(None)
        st.rerun()
