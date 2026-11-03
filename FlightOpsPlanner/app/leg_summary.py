"""Compact flight-leg overview and management controls."""

from collections.abc import Callable
from datetime import datetime, timedelta

import streamlit as st

from app.location_choices import LocationChoice

ACTIVE_LEG_KEY = "flyops_active_editor_leg"
COMPACT_MODE_KEY = "flyops_compact_legs"


def _location_name(
    location_id: str,
    locations: tuple[LocationChoice, ...],
) -> str:
    """Return a readable saved-location name."""

    if not location_id:
        return "Not selected"

    for location in locations:
        if location.location_id == location_id:
            return location.name

    return location_id


def _eta_text(leg: dict) -> str:
    """Calculate the display ETA using the effective ETI."""

    try:
        departure = datetime.combine(
            leg["ETD Date"],
            leg["ETD Time"],
        )
        arrival = departure + timedelta(minutes=float(leg["Flight Minutes"]))
        return arrival.strftime("%H:%M")
    except (KeyError, TypeError, ValueError, OverflowError):
        return "—"


def _eti_indicator(leg: dict) -> str:
    """Return the ETI origin indicator."""

    if leg["Flight Type"] == "Scenic":
        return "🟣 SCHEDULED"

    source = leg.get("_eti_origin", "UNAVAILABLE")

    if source == "AUTO":
        return "🔵 AUTO"

    if source == "MANUAL":
        if leg.get("_eti_review", False):
            return "🟠 MANUAL ⚠️ REVIEW"
        return "🟠 MANUAL"

    return "⚪ UNAVAILABLE"


def activate_leg(uid: str) -> None:
    """Select a leg and enable compact editing."""

    st.session_state[ACTIVE_LEG_KEY] = uid
    st.session_state[COMPACT_MODE_KEY] = True


def render_leg_summary(
    legs: list[dict],
    locations: tuple[LocationChoice, ...],
    *,
    on_add: Callable[[], None],
    on_duplicate: Callable[[str], None],
    on_move: Callable[[str, int], None],
) -> None:
    """Display flight legs with editing and management controls."""

    st.subheader("Flight Leg Overview")

    if not legs:
        st.info("No flight legs have been added.")
        st.button(
            "➕ Add Leg",
            key="summary_add_leg",
            on_click=on_add,
            use_container_width=True,
        )
        return

    valid_ids = {leg["_uid"] for leg in legs}

    if st.session_state.get(ACTIVE_LEG_KEY) not in valid_ids:
        st.session_state[ACTIVE_LEG_KEY] = legs[0]["_uid"]

    st.caption(
        "Edit, duplicate or reorder flights. "
        "Automatic ETI values are recalculated; "
        "manual overrides are preserved and flagged for review."
    )

    for index, leg in enumerate(legs):
        uid = leg["_uid"]

        with st.container(border=True):
            details, controls = st.columns(
                [4, 3],
                vertical_alignment="center",
            )

            with details:
                st.markdown(f"**LEG-{index + 1:03d} — {leg['Flight Type']}**")

                departure = _location_name(
                    leg["Departure"],
                    locations,
                )
                destination = _location_name(
                    leg["Destination"],
                    locations,
                )

                st.write(f"{departure} → {destination}")

                duration = float(leg["Flight Minutes"])
                indicator = _eti_indicator(leg)

                st.caption(
                    f"ETI: {duration:g} min · {indicator} · ETA: {_eta_text(leg)}"
                )

            with controls:
                edit_col, duplicate_col = st.columns(2)

                with edit_col:
                    st.button(
                        "✏️ Edit",
                        key=f"summary_edit_{uid}",
                        on_click=activate_leg,
                        args=(uid,),
                        use_container_width=True,
                    )

                with duplicate_col:
                    st.button(
                        "📋 Duplicate",
                        key=f"summary_duplicate_{uid}",
                        on_click=on_duplicate,
                        args=(uid,),
                        use_container_width=True,
                    )

                up_col, down_col = st.columns(2)

                with up_col:
                    st.button(
                        "⬆️ Up",
                        key=f"summary_up_{uid}",
                        on_click=on_move,
                        args=(uid, -1),
                        disabled=index == 0,
                        use_container_width=True,
                    )

                with down_col:
                    st.button(
                        "⬇️ Down",
                        key=f"summary_down_{uid}",
                        on_click=on_move,
                        args=(uid, 1),
                        disabled=index == len(legs) - 1,
                        use_container_width=True,
                    )

    st.button(
        "➕ Add Leg",
        key="summary_add_leg",
        on_click=on_add,
        type="primary",
        use_container_width=True,
    )
