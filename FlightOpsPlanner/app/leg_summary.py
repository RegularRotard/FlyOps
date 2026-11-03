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


def _etd_indicator(leg: dict, index: int) -> str:
    """Describe whether the departure is scheduled or calculated."""

    source = leg.get("_etd_origin")

    if index == 0:
        return "🟣 SCHEDULED"

    if source == "ADJUSTED":
        return "⚠️ ADJUSTED"

    if source == "MANUAL":
        return "🟠 MANUAL"

    if source == "AUTO":
        return "🔵 AUTO"

    return "⚪ UNKNOWN"


def _etd_text(leg: dict) -> str:
    """Format a departure time for the overview."""

    value = leg.get("ETD Time")

    if value is None:
        return "—"

    try:
        return value.strftime("%H:%M")
    except AttributeError:
        return str(value)[:5]


def _leg_warnings(
    leg: dict,
    locations: tuple[LocationChoice, ...],
    index: int,
) -> list[str]:
    """Return actionable planning warnings for a flight leg."""

    warnings = []

    departure = leg.get("Departure")
    destination = leg.get("Destination")

    if not departure:
        warnings.append("Departure location missing")

    if not destination:
        warnings.append("Destination location missing")

    known = {location.location_id for location in locations}

    if known:
        if departure and departure not in known:
            warnings.append("Departure location not found in catalogue")

        if destination and destination not in known:
            warnings.append("Destination location not found in catalogue")

    try:
        duration = float(leg.get("Flight Minutes", 0))
    except (TypeError, ValueError):
        duration = 0

    if not 0 < duration < float("inf"):
        warnings.append("Valid flight duration required")

    if leg.get("_eti_review", False):
        warnings.append("Manual ETI requires review")

    if leg.get("Flight Type") != "Scenic" and leg.get("_eti_origin") == "UNAVAILABLE":
        warnings.append("Automatic ETI unavailable")

    if index > 0 and leg.get("_etd_origin") == "ADJUSTED":
        warnings.append("Departure adjusted due to scheduling conflict")

    return warnings


def _planning_status(
    leg: dict,
    locations: tuple[LocationChoice, ...],
    index: int,
) -> str:
    """Summarise planning completeness without implying dispatch approval."""

    warnings = _leg_warnings(leg, locations, index)

    if warnings:
        return f"⚠️ {len(warnings)} issue(s)"

    return "✅ No flagged issues"


def render_leg_summary(
    legs: list[dict],
    locations: tuple[LocationChoice, ...],
    *,
    on_add: Callable[[], None],
    on_duplicate: Callable[[str], None],
    on_move: Callable[[str, int], None],
) -> None:
    """Render the compact flight schedule and management controls."""

    st.subheader("Flight Planning Overview")

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

    flagged = sum(
        bool(_leg_warnings(leg, locations, index)) for index, leg in enumerate(legs)
    )

    total_warnings = sum(
        len(_leg_warnings(leg, locations, index)) for index, leg in enumerate(legs)
    )

    metric1, metric2, metric3 = st.columns(3)

    with metric1:
        st.metric("Flight Legs", len(legs))

    with metric2:
        st.metric("Legs with Issues", flagged)

    with metric3:
        st.metric("Planning Warnings", total_warnings)

    if total_warnings:
        st.warning(
            f"{total_warnings} planning warning(s) across "
            f"{flagged} flight leg(s). "
            "Review the highlighted items below."
        )
    else:
        st.success(
            "No planning issues detected by the overview checks. "
            "Operational approval and document validation "
            "are still required."
        )

    st.caption(
        "Departure and flight-duration indicators distinguish "
        "automatically calculated values from manual entries."
    )

    for index, leg in enumerate(legs):
        uid = leg["_uid"]

        departure = _location_name(
            leg.get("Departure", ""),
            locations,
        )

        destination = _location_name(
            leg.get("Destination", ""),
            locations,
        )

        warnings = _leg_warnings(
            leg,
            locations,
            index,
        )

        with st.container(border=True):
            heading, status = st.columns([3, 2])

            with heading:
                st.markdown(
                    f"### LEG-{index + 1:03d} · {leg.get('Flight Type', 'Unknown')}"
                )

            with status:
                st.markdown(_planning_status(leg, locations, index))

            st.write(f"**{departure} → {destination}**")

            etd_col, eti_col, eta_col = st.columns(3)

            with etd_col:
                st.caption("DEPARTURE")
                st.markdown(f"**{_etd_text(leg)}**")
                st.caption(_etd_indicator(leg, index))

            with eti_col:
                st.caption("FLIGHT DURATION")

                try:
                    minutes = float(leg.get("Flight Minutes", 0))
                    duration_text = f"{minutes:g} min"
                except (TypeError, ValueError):
                    duration_text = "—"

                st.markdown(f"**{duration_text}**")
                st.caption(_eti_indicator(leg))

            with eta_col:
                st.caption("ARRIVAL")
                st.markdown(f"**{_eta_text(leg)}**")

            if warnings:
                for warning in warnings:
                    st.caption(f"⚠️ {warning}")

            if leg.get("_etd_origin") == "ADJUSTED":
                requested = leg.get("_etd_requested")

                if requested is not None:
                    try:
                        requested_text = requested.strftime("%d %b %Y %H:%M")
                    except AttributeError:
                        requested_text = str(requested)

                    st.caption(f"Originally requested ETD: {requested_text}")

            edit_col, duplicate_col, up_col, down_col = st.columns(4)

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
