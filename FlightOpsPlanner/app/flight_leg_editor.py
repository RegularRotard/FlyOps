"""Interactive flight-leg editor for FlyOps.

Features:
- Automatic sequential leg numbering
- Individual remove buttons
- Ferry, Charter and Scenic classifications
- Scenic duration restrictions
- Hover explanations for automatic classification changes
"""

from datetime import date, datetime, time
from uuid import uuid4

import pandas as pd
import streamlit as st

from app.etd_tracking import resolve_etd
from app.flight_times import calculate_eta, format_eta
from app.leg_rules import apply_scenic_destination, earliest_etd, enforce_minimum_etd
from app.leg_summary import (
    ACTIVE_LEG_KEY,
    COMPACT_MODE_KEY,
    render_leg_summary,
)
from app.location_choices import (
    format_location_option,
    load_location_choices,
    location_options,
)
from app.new_location_dialog import (
    PENDING_SELECTION_KEY,
    new_location_dialog,
)
from flightops.locations.routing import distance_nm
from flightops.operations.services.eti_calculation import (
    ETISource,
    resolve_eti,
)

FLIGHT_TYPES = ("Ferry", "Charter", "Scenic")

SCENIC_WARNING = (
    "Scenic flights must be either 15 or 30 minutes. "
    "This flight was automatically changed to Charter "
    "because its duration does not match a permitted Scenic block."
)

EDITOR_STATE_KEY = "flyops_leg_editor_rows"


def _new_leg(
    departure_datetime: datetime | None = None,
) -> dict:
    """Create a new leg with a stable internal identifier."""

    if departure_datetime is None:
        departure_date = date.today()
        departure_time = time(8, 0)
    else:
        departure_date = departure_datetime.date()
        departure_time = departure_datetime.time().replace(
            second=0,
            microsecond=0,
        )

    return {
        "_uid": uuid4().hex,
        "Flight Type": "Charter",
        "Departure": "",
        "Destination": "",
        "ETD Date": departure_date,
        "ETD Time": departure_time,
        "_etd_mode": "AUTO",
        "_etd_origin": "AUTO",
        "_etd_requested": None,
        "Flight Minutes": 30.0,
        "Additional Idle": 0.0,
        "Shutdown": True,
        "_scenic_warning": False,
        "_eti_mode": "AUTO",
        "_eti_manual_context": None,
        "_eti_current_context": None,
        "_eti_origin": "UNAVAILABLE",
        "_eti_auto_minutes": None,
        "_eti_review": False,
    }


def _find_leg(uid: str) -> dict:
    """Return a leg by its stable internal identifier."""

    for leg in st.session_state[EDITOR_STATE_KEY]:
        if leg["_uid"] == uid:
            return leg

    raise ValueError(f"Unknown flight-leg editor ID: {uid}")


def _initialise_editor(existing: pd.DataFrame) -> None:
    """Initialise editor data from the existing flight schedule."""

    if EDITOR_STATE_KEY in st.session_state:
        return

    legs = []

    for _, row in existing.iterrows():
        leg = _new_leg()

        flight_type = str(row.get("Flight Type", "Charter"))

        if flight_type not in FLIGHT_TYPES:
            flight_type = "Charter"

        minutes = float(row.get("Flight Minutes", 30.0))

        warning = flight_type == "Scenic" and minutes not in (15.0, 30.0)

        if warning:
            flight_type = "Charter"

        leg.update(
            {
                "Flight Type": flight_type,
                "Departure": str(row.get("Departure", "")),
                "Destination": str(row.get("Destination", "")),
                "Flight Minutes": minutes,
                "Additional Idle": float(row.get("Additional Idle", 0.0)),
                "Shutdown": bool(row.get("Shutdown", True)),
                "_scenic_warning": warning,
                "_etd_mode": (
                    "MANUAL"
                    if str(row.get("ETD Source", "AUTO")) in ("MANUAL", "ADJUSTED")
                    else "AUTO"
                ),
                "_eti_mode": (
                    str(row.get("ETI Source", "AUTO"))
                    if str(row.get("ETI Source", "AUTO")) in ("AUTO", "MANUAL")
                    else "AUTO"
                ),
                "ETD Date": (
                    row["ETD Date"]
                    if isinstance(row.get("ETD Date"), date)
                    else date.fromisoformat(str(row["ETD Date"]))
                    if pd.notna(row.get("ETD Date"))
                    else date.today()
                ),
                "ETD Time": (
                    row["ETD Time"]
                    if isinstance(row.get("ETD Time"), time)
                    else time.fromisoformat(str(row["ETD Time"]))
                    if pd.notna(row.get("ETD Time"))
                    else time(8, 0)
                ),
            }
        )

        apply_scenic_destination(leg)
        enforce_minimum_etd(leg, legs[-1] if legs else None)
        legs.append(leg)

    st.session_state[EDITOR_STATE_KEY] = legs


def _add_leg() -> None:
    """Append a leg with ETD defaulting to the previous ETA."""

    legs = st.session_state[EDITOR_STATE_KEY]

    if not legs:
        legs.append(_new_leg())
        return

    previous = legs[-1]

    previous_eta = calculate_eta(
        previous["ETD Date"],
        previous["ETD Time"],
        float(previous["Flight Minutes"]),
    )

    new_leg = _new_leg(
        departure_datetime=previous_eta,
    )

    # The next leg begins where the previous leg finished.
    new_leg["Departure"] = previous["Destination"]

    legs.append(new_leg)


def _remove_leg(uid: str) -> None:
    """Remove the selected flight leg."""

    st.session_state[EDITOR_STATE_KEY] = [
        leg for leg in st.session_state[EDITOR_STATE_KEY] if leg["_uid"] != uid
    ]


def _update_field(uid: str, field: str) -> None:
    """Copy a widget value into the editor's data model."""

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise
    widget_key = f"{field}_{uid}"

    leg[field] = st.session_state[widget_key]
    if field in ("ETD Date", "ETD Time"):
        legs = st.session_state[EDITOR_STATE_KEY]
        first = bool(legs and legs[0]["_uid"] == uid)
        if first:
            leg["_etd_mode"] = "SCHEDULED"
            leg["_etd_origin"] = "SCHEDULED"
            leg["_etd_requested"] = None
        else:
            leg["_etd_mode"] = "MANUAL"
            leg["_etd_requested"] = datetime.combine(leg["ETD Date"], leg["ETD Time"])
    if field == "Departure":
        apply_scenic_destination(leg)
        if leg["Flight Type"] == "Scenic":
            st.session_state[f"Destination_{uid}"] = leg["Destination"]


def _flight_type_changed(uid: str) -> None:
    """Apply flight-type rules when the type is changed."""

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    selected_type = st.session_state[f"Flight Type_{uid}"]

    leg["Flight Type"] = selected_type
    leg["_eti_mode"] = "AUTO"
    leg["_eti_manual_context"] = None
    leg["_scenic_warning"] = False

    if selected_type != "Scenic":
        st.session_state[f"Flight Minutes_{uid}"] = max(
            1.0,
            float(leg["Flight Minutes"]),
        )

    apply_scenic_destination(leg)
    if selected_type == "Scenic":
        st.session_state[f"Destination_{uid}"] = leg["Destination"]

    # Selecting Scenic starts with a valid 15-minute block.
    if selected_type == "Scenic" and leg["Flight Minutes"] not in (15.0, 30.0):
        leg["Flight Minutes"] = 15.0

        st.session_state[f"Flight Minutes_{uid}"] = 15.0


def _duration_changed(uid: str) -> None:
    """Automatically convert invalid Scenic durations to Charter."""

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    minutes = float(st.session_state[f"Flight Minutes_{uid}"])

    leg["Flight Minutes"] = minutes
    if leg["Flight Type"] != "Scenic":
        leg["_eti_mode"] = "MANUAL"
        leg["_eti_manual_context"] = leg.get("_eti_current_context")

    if leg["Flight Type"] == "Scenic" and minutes not in (15.0, 30.0):
        leg["Flight Type"] = "Charter"
        leg["_scenic_warning"] = True

        st.session_state[f"Flight Type_{uid}"] = "Charter"


def _sync_widget_value(uid: str, field: str, value: object) -> None:
    """Synchronise a widget before it is instantiated on this rerun."""
    key = f"{field}_{uid}"
    if key in st.session_state:
        st.session_state[key] = value


def _apply_etd_tracking(
    leg: dict,
    previous: dict | None,
) -> None:
    """Resolve ETD and synchronise date/time widgets."""

    current = datetime.combine(
        leg["ETD Date"],
        leg["ETD Time"],
    )

    previous_eta = earliest_etd(previous)

    manual_requested = (
        leg.get("_etd_requested") if leg.get("_etd_mode") == "MANUAL" else None
    )

    if leg.get("_etd_mode") == "MANUAL" and manual_requested is None:
        manual_requested = current
        leg["_etd_requested"] = current

    result = resolve_etd(
        current=current,
        previous_eta=previous_eta,
        manual_requested=manual_requested,
    )

    leg["_etd_origin"] = result.source.value

    if result.departure != current:
        leg["ETD Date"] = result.departure.date()
        leg["ETD Time"] = result.departure.time()

        _sync_widget_value(
            leg["_uid"],
            "ETD Date",
            leg["ETD Date"],
        )

        _sync_widget_value(
            leg["_uid"],
            "ETD Time",
            leg["ETD Time"],
        )


def _reset_etd_to_auto(uid: str) -> None:
    """Clear a manual departure-time override."""

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    leg["_etd_mode"] = "AUTO"
    leg["_etd_requested"] = None
    leg["_etd_origin"] = "AUTO"


def _prepare_leg_for_render(leg: dict, previous: dict | None) -> None:
    """Apply route and scheduling rules before constructing Streamlit widgets."""
    uid = leg["_uid"]
    old_destination = leg["Destination"]
    apply_scenic_destination(leg)
    if old_destination != leg["Destination"]:
        _sync_widget_value(uid, "Destination", leg["Destination"])

    _apply_etd_tracking(leg, previous)


def _resolve_editor_eti(
    leg: dict,
    saved_locations: tuple,
    groundspeed_knots: float,
) -> None:
    """Resolve ETI while preserving explicit manual overrides."""

    if leg["Flight Type"] == "Scenic":
        leg["_eti_origin"] = "SCHEDULED"
        leg["_eti_auto_minutes"] = None
        leg["_eti_review"] = False
        return

    locations = {location.location_id: location for location in saved_locations}

    departure = locations.get(leg["Departure"])
    destination = locations.get(leg["Destination"])

    distance = None

    if departure is not None and destination is not None:
        distance = distance_nm(
            departure.latitude,
            departure.longitude,
            destination.latitude,
            destination.longitude,
        )

    # A zero-distance Charter/Ferry route has no usable automatic ETI.
    if distance is not None and distance <= 0:
        distance = None

    context = (
        leg["Departure"],
        leg["Destination"],
        float(groundspeed_knots),
        ((departure.latitude, departure.longitude) if departure is not None else None),
        (
            (destination.latitude, destination.longitude)
            if destination is not None
            else None
        ),
    )

    leg["_eti_current_context"] = context

    if float(leg["Flight Minutes"]) < 1.0:
        leg["Flight Minutes"] = 1.0

    manual = leg.get("_eti_mode") == "MANUAL"

    result = resolve_eti(
        flight_type=leg["Flight Type"],
        distance_nm=distance,
        groundspeed_knots=groundspeed_knots,
        manual_minutes=(float(leg["Flight Minutes"]) if manual else None),
        route_changed=(manual and leg.get("_eti_manual_context") != context),
    )

    leg["_eti_origin"] = result.source.value
    leg["_eti_auto_minutes"] = result.calculated_minutes
    leg["_eti_review"] = result.requires_review

    if result.source == ETISource.AUTO:
        calculated = float(result.minutes)

        if float(leg["Flight Minutes"]) != calculated:
            leg["Flight Minutes"] = calculated

            _sync_widget_value(
                leg["_uid"],
                "Flight Minutes",
                calculated,
            )


def _reset_eti_to_auto(uid: str) -> None:
    """Remove a manual ETI override."""

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    leg["_eti_mode"] = "AUTO"
    leg["_eti_manual_context"] = None
    leg["_eti_review"] = False


def _set_scenic_duration(uid: str, minutes: int) -> None:
    """Set a permitted Scenic duration directly from a button."""

    if minutes not in (15, 30):
        raise ValueError("Scenic duration must be 15 or 30 minutes.")

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    if leg["Flight Type"] != "Scenic":
        return

    leg["Flight Minutes"] = float(minutes)
    leg["_eti_origin"] = "SCHEDULED"
    leg["_eti_mode"] = "AUTO"
    leg["_eti_manual_context"] = None
    leg["_eti_review"] = False


def _render_leg(
    leg: dict,
    sequence: int,
    saved_locations: tuple,
) -> None:
    """Render one editable flight-leg card."""

    uid = leg["_uid"]

    with st.container(border=True):
        header, warning_column, remove_column = st.columns(
            [5, 1, 2],
            vertical_alignment="center",
        )

        with header:
            st.subheader(f"LEG-{sequence:03d} — {leg['Flight Type']}")

        with warning_column:
            if leg["_scenic_warning"]:
                st.button(
                    "⚠️",
                    key=f"warning_{uid}",
                    help=SCENIC_WARNING,
                    type="tertiary",
                )

        with remove_column:
            st.button(
                "🗑️ Remove",
                key=f"remove_{uid}",
                on_click=_remove_leg,
                args=(uid,),
                use_container_width=True,
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.selectbox(
                "Flight Type",
                options=FLIGHT_TYPES,
                index=FLIGHT_TYPES.index(leg["Flight Type"]),
                key=f"Flight Type_{uid}",
                on_change=_flight_type_changed,
                args=(uid,),
            )
        with col2:
            departure_options = location_options(
                saved_locations,
                leg["Departure"],
            )

            st.selectbox(
                "Departure 🔗" if sequence > 1 else "Departure",
                options=departure_options,
                index=departure_options.index(leg["Departure"]),
                format_func=lambda location_id: format_location_option(
                    location_id,
                    saved_locations,
                ),
                key=f"Departure_{uid}",
                disabled=sequence > 1,
                on_change=(_update_field if sequence == 1 else None),
                args=((uid, "Departure") if sequence == 1 else ()),
                help=(
                    "Automatically linked to the previous leg's destination."
                    if sequence > 1
                    else "Select the departure location."
                ),
            )

        with col3:
            destination_options = location_options(
                saved_locations,
                leg["Destination"],
            )

            scenic = leg["Flight Type"] == "Scenic"

            st.selectbox(
                "Destination 🔗" if scenic else "Destination",
                options=destination_options,
                index=destination_options.index(leg["Destination"]),
                format_func=lambda location_id: format_location_option(
                    location_id,
                    saved_locations,
                ),
                key=f"Destination_{uid}",
                disabled=scenic,
                on_change=None if scenic else _update_field,
                args=() if scenic else (uid, "Destination"),
                help=(
                    "Scenic flights return to their departure location."
                    if scenic
                    else "Type a location name or identifier to search."
                ),
            )
        new_departure_col, new_destination_col = st.columns(2)

        with new_departure_col:
            if st.button(
                "➕ New Departure",
                key=f"new_departure_{uid}",
                use_container_width=True,
                disabled=sequence > 1,
                help=(
                    "For subsequent legs, departure is automatically "
                    "linked to the previous destination."
                ),
            ):
                new_location_dialog(uid, "Departure")

        with new_destination_col:
            if st.button(
                "➕ New Destination",
                key=f"new_destination_{uid}",
                use_container_width=True,
                disabled=leg["Flight Type"] == "Scenic",
                help=(
                    "Scenic destinations are automatically linked to their departure."
                ),
            ):
                new_location_dialog(uid, "Destination")

        st.markdown("#### Flight Timing")
        legs = st.session_state[EDITOR_STATE_KEY]

        previous = next(
            (
                legs[index - 1]
                for index, item in enumerate(legs)
                if item["_uid"] == uid and index > 0
            ),
            None,
        )
        minimum = earliest_etd(previous)
        if minimum is not None:
            st.caption(
                "Earliest permitted ETD: "
                f"{minimum:%d %b %Y %H:%M} "
                "(previous leg ETA; later times remain editable)."
            )

        timing_col1, timing_col2, timing_col3, timing_col4 = st.columns(4)

        etd_origin = leg.get("_etd_origin", "SCHEDULED")

        if etd_origin == "AUTO":
            st.caption("🔵 AUTO · Departure")
        elif etd_origin == "MANUAL":
            st.caption("🟠 MANUAL · Departure")
        elif etd_origin == "ADJUSTED":
            st.caption("⚠️ ADJUSTED · Departure")
            requested = leg.get("_etd_requested")
            if requested is not None:
                st.warning(
                    f"Originally requested: {requested:%d %b %Y %H:%M}. "
                    "FlyOps adjusted the departure to avoid an overlap."
                )
        else:
            st.caption("🟣 SCHEDULED · First departure")

        if previous is not None and etd_origin in (
            "MANUAL",
            "ADJUSTED",
        ):
            st.button(
                "↺ Reset ETD to Auto",
                key=f"reset_etd_{uid}",
                on_click=_reset_etd_to_auto,
                args=(uid,),
            )

        with timing_col1:
            st.date_input(
                "ETD Date",
                value=leg["ETD Date"],
                key=f"ETD Date_{uid}",
                min_value=minimum.date() if minimum else None,
                on_change=_update_field,
                args=(uid, "ETD Date"),
            )

        with timing_col2:
            st.time_input(
                "ETD",
                value=leg["ETD Time"],
                step=60,
                key=f"ETD Time_{uid}",
                help="If earlier than the previous ETA, FlyOps will adjust it automatically.",
                on_change=_update_field,
                args=(uid, "ETD Time"),
            )

        with timing_col3:
            origin = leg.get("_eti_origin", "UNAVAILABLE")

            if leg["Flight Type"] == "Scenic":
                # Scenic durations are scheduled products, not route ETIs.
                if float(leg["Flight Minutes"]) not in (15.0, 30.0):
                    leg["Flight Minutes"] = 15.0

                st.caption("🟣 SCHEDULED · Scenic duration")

                scenic_15, scenic_30 = st.columns(2)

                with scenic_15:
                    st.button(
                        "15 MIN",
                        key=f"scenic_15_{uid}",
                        type=(
                            "primary" if leg["Flight Minutes"] == 15.0 else "secondary"
                        ),
                        on_click=_set_scenic_duration,
                        args=(uid, 15),
                        use_container_width=True,
                    )

                with scenic_30:
                    st.button(
                        "30 MIN",
                        key=f"scenic_30_{uid}",
                        type=(
                            "primary" if leg["Flight Minutes"] == 30.0 else "secondary"
                        ),
                        on_click=_set_scenic_duration,
                        args=(uid, 30),
                        use_container_width=True,
                    )

            else:
                if origin == "AUTO":
                    st.caption("🔵 AUTO · Calculated")
                elif origin == "MANUAL":
                    if leg.get("_eti_review"):
                        st.caption("🟠 MANUAL · ⚠️ REVIEW")
                    else:
                        st.caption("🟠 MANUAL · Override")
                else:
                    st.caption("⚪ NOT CALCULATED")

                # Always normalise BEFORE creating the widget.
                minutes = float(leg["Flight Minutes"])

                if minutes < 1.0:
                    minutes = 1.0
                    leg["Flight Minutes"] = minutes

                widget_key = f"Flight Minutes_{uid}"

                if (
                    widget_key not in st.session_state
                    or float(st.session_state[widget_key]) < 1.0
                ):
                    st.session_state[widget_key] = minutes

                # No value= argument: Session State owns this widget.
                st.number_input(
                    "ETI (minutes)",
                    min_value=1.0,
                    step=1.0,
                    key=widget_key,
                    on_change=_duration_changed,
                    args=(uid,),
                )

                calculated = leg.get("_eti_auto_minutes")

                if origin == "MANUAL":
                    if calculated is not None:
                        st.caption(f"Automatic estimate: {calculated:.0f} min")

                    st.button(
                        "↺ Reset to Auto",
                        key=f"reset_eti_{uid}",
                        on_click=_reset_eti_to_auto,
                        args=(uid,),
                        use_container_width=True,
                    )

                    if leg.get("_eti_review"):
                        st.warning(
                            "Route or planning speed changed after "
                            "this ETI was manually entered. "
                            "Review the duration or reset to Auto."
                        )

                elif origin == "AUTO":
                    st.caption(
                        "Updates when the route or planning groundspeed changes."
                    )

        eta = calculate_eta(
            leg["ETD Date"],
            leg["ETD Time"],
            float(leg["Flight Minutes"]),
        )

        with timing_col4:
            st.text_input(
                "ETA (calculated)",
                value=format_eta(eta, leg["ETD Date"]),
                disabled=True,
            )
        ground_col1, ground_col2 = st.columns(2)

        with ground_col1:
            st.number_input(
                "Additional Idle (minutes)",
                min_value=0.0,
                step=1.0,
                value=float(leg["Additional Idle"]),
                key=f"Additional Idle_{uid}",
                on_change=_update_field,
                args=(uid, "Additional Idle"),
            )

        with ground_col2:
            st.checkbox(
                "Shutdown after flight",
                value=bool(leg["Shutdown"]),
                key=f"Shutdown_{uid}",
                on_change=_update_field,
                args=(uid, "Shutdown"),
            )


def _apply_pending_location_selection() -> None:
    """Apply a newly created location before rendering editor widgets."""

    pending = st.session_state.pop(
        PENDING_SELECTION_KEY,
        None,
    )

    if not pending:
        return

    uid = pending["uid"]
    field = pending["field"]
    location_id = pending["location_id"]

    if field not in ("Departure", "Destination"):
        return

    try:
        leg = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    leg[field] = location_id

    _sync_widget_value(
        uid,
        field,
        location_id,
    )

    if field == "Departure":
        apply_scenic_destination(leg)

        if leg["Flight Type"] == "Scenic":
            _sync_widget_value(
                uid,
                "Destination",
                leg["Destination"],
            )


def _select_compact_leg(uid: str) -> None:
    """Open the specified leg in compact mode."""

    st.session_state[ACTIVE_LEG_KEY] = uid
    st.session_state[COMPACT_MODE_KEY] = True


def _add_leg_from_summary() -> None:
    """Append a flight leg and open it for editing."""

    _add_leg()

    legs = st.session_state[EDITOR_STATE_KEY]

    if legs:
        _select_compact_leg(legs[-1]["_uid"])


def _reflow_leg_sequence(start_index: int = 1) -> None:
    """Recalculate affected legs in chronological order."""

    legs = st.session_state[EDITOR_STATE_KEY]

    try:
        saved_locations = load_location_choices()
    except (OSError, ValueError):
        saved_locations = ()

    groundspeed = float(
        st.session_state.get(
            "flyops_map_cruise_speed",
            100.0,
        )
    )

    for index in range(max(0, start_index), len(legs)):
        leg = legs[index]

        if index > 0:
            previous = legs[index - 1]

            # Maintain route continuity.
            leg["Departure"] = previous["Destination"]

            _sync_widget_value(
                leg["_uid"],
                "Departure",
                leg["Departure"],
            )

        old_destination = leg["Destination"]

        apply_scenic_destination(leg)

        if old_destination != leg["Destination"]:
            _sync_widget_value(
                leg["_uid"],
                "Destination",
                leg["Destination"],
            )

        # Update ETI using the newly resolved route.
        # Manual overrides remain unchanged.
        _resolve_editor_eti(
            leg,
            saved_locations,
            groundspeed,
        )

        # Recalculate ETD after the updated route and ETI.
        _apply_etd_tracking(
            leg,
            legs[index - 1] if index > 0 else None,
        )


def _duplicate_leg(uid: str) -> None:
    """Duplicate a leg with a new identity and valid schedule position."""

    from copy import deepcopy

    try:
        original = _find_leg(uid)
    except ValueError as exc:
        if str(exc).startswith("Unknown flight-leg editor ID:"):
            return
        raise

    legs = st.session_state[EDITOR_STATE_KEY]
    index = next(i for i, leg in enumerate(legs) if leg["_uid"] == uid)

    new_leg = deepcopy(original)
    new_leg["_uid"] = uuid4().hex
    new_leg["_scenic_warning"] = False
    new_leg["_etd_mode"] = "AUTO"
    new_leg["_etd_origin"] = "AUTO"
    new_leg["_etd_requested"] = None

    # The duplicate starts after the original finishes.
    next_departure = earliest_etd(original)

    if next_departure is not None:
        new_leg["ETD Date"] = next_departure.date()
        new_leg["ETD Time"] = next_departure.time().replace(
            second=0,
            microsecond=0,
        )

    new_leg["Departure"] = original["Destination"]

    apply_scenic_destination(new_leg)

    # A duplicated manual ETI remains manual but requires review.
    if new_leg.get("_eti_mode") == "MANUAL":
        new_leg["_eti_manual_context"] = None
        new_leg["_eti_review"] = True

    legs.insert(index + 1, new_leg)

    _reflow_leg_sequence(index + 1)

    _select_compact_leg(new_leg["_uid"])


def _move_leg(uid: str, direction: int) -> None:
    """Move one flight leg and rebuild dependent route connections."""

    if direction not in (-1, 1):
        raise ValueError("Direction must be -1 or 1.")

    legs = st.session_state[EDITOR_STATE_KEY]

    index = next(
        (i for i, leg in enumerate(legs) if leg["_uid"] == uid),
        None,
    )

    if index is None:
        return

    destination_index = index + direction

    if not 0 <= destination_index < len(legs):
        return

    legs[index], legs[destination_index] = (
        legs[destination_index],
        legs[index],
    )

    first_affected = min(index, destination_index)

    # Reordered manual ETI values must be explicitly reviewed.
    for leg in legs[first_affected:]:
        if leg.get("_eti_mode") == "MANUAL":
            leg["_eti_manual_context"] = None
            leg["_eti_review"] = True

    _reflow_leg_sequence(first_affected)

    _select_compact_leg(uid)


def render_flight_leg_editor(
    existing: pd.DataFrame,
) -> pd.DataFrame:
    """Render flight legs and return the validated editor data structure.

    Leg numbering is derived from list position rather than entered manually.
    Existing backend validation remains responsible for route continuity,
    unique identifiers and operational flight-planning constraints.
    """

    _initialise_editor(existing)
    _apply_pending_location_selection()
    try:
        saved_locations = load_location_choices()
    except (OSError, ValueError) as error:
        saved_locations = ()
        st.warning(f"Saved locations unavailable: {error}")
    st.subheader("Flight Legs")

    st.caption(
        "Leg numbers are assigned automatically. "
        "Use the Remove button on any leg to delete it."
    )

    legs = st.session_state[EDITOR_STATE_KEY]

    for index, leg in enumerate(legs, start=1):
        _prepare_leg_for_render(leg, legs[index - 2] if index > 1 else None)
        _resolve_editor_eti(
            leg,
            saved_locations,
            float(st.session_state.get("flyops_map_cruise_speed", 100.0)),
        )

    render_leg_summary(
        legs,
        saved_locations,
        on_add=_add_leg_from_summary,
        on_duplicate=_duplicate_leg,
        on_move=_move_leg,
    )

    compact_mode = st.toggle(
        "Compact leg editor",
        key=COMPACT_MODE_KEY,
        help="Show only the selected leg while editing.",
    )

    active_uid = st.session_state.get(ACTIVE_LEG_KEY)

    for index, leg in enumerate(legs, start=1):
        if not compact_mode or leg["_uid"] == active_uid:
            _render_leg(leg, index, saved_locations)

    st.button(
        "➕ Add Flight Leg",
        on_click=_add_leg,
        type="secondary",
        use_container_width=True,
    )

    if not legs:
        st.warning(
            "No flight legs are currently defined. Add a flight leg to begin planning."
        )

    rows = []
    for index, leg in enumerate(legs, start=1):
        eta = calculate_eta(
            leg["ETD Date"],
            leg["ETD Time"],
            float(leg["Flight Minutes"]),
        )
        rows.append(
            {
                "Leg": f"LEG-{index:03d}",
                "Flight Type": leg["Flight Type"],
                "Departure": leg["Departure"],
                "Destination": leg["Destination"],
                "Flight Minutes": leg["Flight Minutes"],
                "Additional Idle": leg["Additional Idle"],
                "ETD Date": leg["ETD Date"].isoformat(),
                "ETD Time": leg["ETD Time"].strftime("%H:%M"),
                "ETD Source": leg.get("_etd_origin", "SCHEDULED"),
                "ETD Requested": (
                    leg["_etd_requested"].isoformat(timespec="minutes")
                    if leg.get("_etd_requested") is not None
                    else None
                ),
                "ETI Minutes": leg["Flight Minutes"],
                "ETI Source": leg.get("_eti_origin", "UNAVAILABLE"),
                "Auto ETI Minutes": leg.get("_eti_auto_minutes"),
                "ETI Review Required": leg.get("_eti_review", False),
                "ETA": eta.isoformat(timespec="minutes"),
                "Shutdown": leg["Shutdown"],
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "Leg",
            "Flight Type",
            "Departure",
            "Destination",
            "ETD Date",
            "ETD Time",
            "ETD Source",
            "ETD Requested",
            "ETI Minutes",
            "ETI Source",
            "Auto ETI Minutes",
            "ETI Review Required",
            "ETA",
            "Flight Minutes",
            "Additional Idle",
            "Shutdown",
        ],
    )
