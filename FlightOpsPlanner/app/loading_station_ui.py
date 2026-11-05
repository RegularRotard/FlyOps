"""Compact aircraft loading-station assignment interface."""

import streamlit as st

from flightops.operations.loading.manifest_adapter import (
    LegStationAssignments,
)
from flightops.operations.loading.revision_bridge import (
    StationOption,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)

LOADING_STATE_KEY = "flyops_leg_station_assignments"
LOADING_REVISION_KEY = "flyops_loading_revision_identity"


def _initialise_loading_state(
    *,
    aircraft_profile_id: str,
    revision_id: str,
    leg_uids: list[str],
) -> dict:
    """Keep station assignments bound to the selected aircraft revision."""

    state = st.session_state

    identity = (
        aircraft_profile_id,
        revision_id,
    )

    if state.get(LOADING_REVISION_KEY) != identity:
        state[LOADING_STATE_KEY] = {}
        state[LOADING_REVISION_KEY] = identity

    assignments = state.setdefault(
        LOADING_STATE_KEY,
        {},
    )

    valid_legs = set(leg_uids)

    for uid in list(assignments):
        if uid not in valid_legs:
            del assignments[uid]

    for uid in leg_uids:
        assignments.setdefault(
            uid,
            {
                "passengers": {},
                "baggage": {},
            },
        )

    return assignments


def _station_options(
    stations: tuple[StationOption, ...],
) -> tuple[str, ...]:
    """Return station IDs with an empty option for unassigned loads."""

    return ("", *(station.station_id for station in stations))


def _station_label(
    station_id: str,
    stations: tuple[StationOption, ...],
) -> str:
    if not station_id:
        return "Select station"

    for station in stations:
        if station.station_id == station_id:
            return station.name

    return f"Unknown station: {station_id}"


def _save_station_selection(
    leg_uid: str,
    record_type: str,
    record_id: str,
    widget_key: str,
) -> None:
    """Store one station selection against its leg and manifest record."""

    assignments = st.session_state[LOADING_STATE_KEY]

    leg_assignments = assignments.get(leg_uid)

    if leg_assignments is None:
        return

    station_id = st.session_state.get(
        widget_key,
        "",
    )

    if station_id:
        leg_assignments[record_type][record_id] = station_id
    else:
        leg_assignments[record_type].pop(
            record_id,
            None,
        )


def render_loading_station_ui(
    *,
    manifests: list[LegManifest],
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
    stations: tuple[StationOption, ...],
    aircraft_profile_id: str,
    revision_id: str,
) -> dict[str, LegStationAssignments]:
    """Render compact loading assignments for all manifest legs.

    A caller must supply stations from the selected aircraft
    configuration revision.
    """

    uids = [manifest.leg_uid for manifest in manifests]

    assignments = _initialise_loading_state(
        aircraft_profile_id=aircraft_profile_id,
        revision_id=revision_id,
        leg_uids=uids,
    )

    options = _station_options(stations)

    st.markdown("**Aircraft Loading Stations**")

    st.caption("Station selections use the aircraft's selected configuration revision.")

    for index, manifest in enumerate(manifests, start=1):
        uid = manifest.leg_uid

        leg_assignments = assignments[uid]

        # Remove station assignments for records no longer onboard.
        for record_type, valid_ids in (
            ("passengers", manifest.passenger_ids),
            ("baggage", manifest.baggage_ids),
        ):
            for record_id in list(leg_assignments[record_type]):
                if record_id not in valid_ids:
                    del leg_assignments[record_type][record_id]

        if not manifest.passenger_ids and not manifest.baggage_ids:
            continue

        st.markdown(f"**LEG-{index:03d}**")

        records = [
            (
                "passengers",
                passenger_id,
                passengers[passenger_id].name,
                passengers[passenger_id].effective_weight_kg,
            )
            for passenger_id in sorted(manifest.passenger_ids)
            if passenger_id in passengers
        ]

        records.extend(
            (
                "baggage",
                baggage_id,
                baggage[baggage_id].description,
                baggage[baggage_id].effective_weight_kg,
            )
            for baggage_id in sorted(manifest.baggage_ids)
            if baggage_id in baggage
        )

        for record_type, record_id, name, weight in records:
            columns = st.columns(
                [2.5, 1, 2],
                vertical_alignment="center",
            )

            with columns[0]:
                st.write(name)

            with columns[1]:
                if weight is None:
                    st.write("⚠️ No weight")
                else:
                    st.write(f"{weight:.1f} kg")

            with columns[2]:
                current = leg_assignments[record_type].get(record_id, "")

                if current not in options:
                    current = ""

                key = (
                    f"load_station_"
                    f"{aircraft_profile_id}_"
                    f"{revision_id}_"
                    f"{uid}_"
                    f"{record_type}_"
                    f"{record_id}"
                )

                st.selectbox(
                    f"Station for {name}",
                    options,
                    index=options.index(current),
                    format_func=lambda station_id: _station_label(
                        station_id,
                        stations,
                    ),
                    key=key,
                    on_change=_save_station_selection,
                    args=(
                        uid,
                        record_type,
                        record_id,
                        key,
                    ),
                    label_visibility="collapsed",
                )

    return {
        uid: LegStationAssignments(
            leg_uid=uid,
            passenger_stations=dict(assignments[uid]["passengers"]),
            baggage_stations=dict(assignments[uid]["baggage"]),
        )
        for uid in uids
    }
