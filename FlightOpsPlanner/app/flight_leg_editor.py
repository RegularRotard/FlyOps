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

from app.flight_times import calculate_eta, format_eta
from app.leg_rules import apply_scenic_destination, earliest_etd, enforce_minimum_etd

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
        "Flight Minutes": 30.0,
        "Additional Idle": 0.0,
        "Shutdown": True,
        "_scenic_warning": False,
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

    leg = _find_leg(uid)
    widget_key = f"{field}_{uid}"

    leg[field] = st.session_state[widget_key]
    if field == "Departure":
        apply_scenic_destination(leg)
        if leg["Flight Type"] == "Scenic":
            st.session_state[f"Destination_{uid}"] = leg["Destination"]


def _flight_type_changed(uid: str) -> None:
    """Apply flight-type rules when the type is changed."""

    leg = _find_leg(uid)

    selected_type = st.session_state[f"Flight Type_{uid}"]

    leg["Flight Type"] = selected_type
    leg["_scenic_warning"] = False
    apply_scenic_destination(leg)
    if selected_type == "Scenic":
        st.session_state[f"Destination_{uid}"] = leg["Destination"]

    # Selecting Scenic starts with a valid 15-minute block.
    if selected_type == "Scenic" and leg["Flight Minutes"] not in (15.0, 30.0):
        leg["Flight Minutes"] = 15.0

        st.session_state[f"Flight Minutes_{uid}"] = 15.0


def _duration_changed(uid: str) -> None:
    """Automatically convert invalid Scenic durations to Charter."""

    leg = _find_leg(uid)

    minutes = float(st.session_state[f"Flight Minutes_{uid}"])

    leg["Flight Minutes"] = minutes

    if leg["Flight Type"] == "Scenic" and minutes not in (15.0, 30.0):
        leg["Flight Type"] = "Charter"
        leg["_scenic_warning"] = True

        st.session_state[f"Flight Type_{uid}"] = "Charter"


def _sync_widget_value(uid: str, field: str, value: object) -> None:
    """Synchronise a widget before it is instantiated on this rerun."""
    key = f"{field}_{uid}"
    if key in st.session_state:
        st.session_state[key] = value


def _prepare_leg_for_render(leg: dict, previous: dict | None) -> None:
    """Apply route and scheduling rules before constructing Streamlit widgets."""
    uid = leg["_uid"]
    old_destination = leg["Destination"]
    apply_scenic_destination(leg)
    if old_destination != leg["Destination"]:
        _sync_widget_value(uid, "Destination", leg["Destination"])

    if enforce_minimum_etd(leg, previous):
        _sync_widget_value(uid, "ETD Date", leg["ETD Date"])
        _sync_widget_value(uid, "ETD Time", leg["ETD Time"])


def _render_leg(leg: dict, sequence: int) -> None:
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
            st.text_input(
                "Departure",
                value=leg["Departure"],
                key=f"Departure_{uid}",
                on_change=_update_field,
                args=(uid, "Departure"),
            )

        with col3:
            st.text_input(
                "Destination",
                value=leg["Destination"],
                key=f"Destination_{uid}",
                disabled=leg["Flight Type"] == "Scenic",
                help="Scenic flights return to the departure location.",
                on_change=_update_field,
                args=(uid, "Destination"),
            )
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
            st.number_input(
                "ETI (minutes)",
                min_value=1.0,
                step=1.0,
                value=float(leg["Flight Minutes"]),
                key=f"Flight Minutes_{uid}",
                on_change=_duration_changed,
                args=(uid,),
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


def render_flight_leg_editor(
    existing: pd.DataFrame,
) -> pd.DataFrame:
    """Render flight legs and return the validated editor data structure.

    Leg numbering is derived from list position rather than entered manually.
    Existing backend validation remains responsible for route continuity,
    unique identifiers and operational flight-planning constraints.
    """

    _initialise_editor(existing)

    st.subheader("Flight Legs")

    st.caption(
        "Leg numbers are assigned automatically. "
        "Use the Remove button on any leg to delete it."
    )

    legs = st.session_state[EDITOR_STATE_KEY]

    for index, leg in enumerate(legs, start=1):
        _prepare_leg_for_render(leg, legs[index - 2] if index > 1 else None)
        _render_leg(leg, index)

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
                "ETI Minutes": leg["Flight Minutes"],
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
            "ETI Minutes",
            "ETA",
            "Flight Minutes",
            "Additional Idle",
            "Shutdown",
        ],
    )
