"""Compact crew and fuel inputs for revision-bound W&B."""

import streamlit as st

from app.leg_wb_input_service import (
    LoadingInputError,
    build_leg_conditions,
)
from flightops.crew.roster import load_pilots
from flightops.operations.loading.leg_conditions import (
    LegConditionError,
)
from flightops.operations.loading.revision_bridge import (
    StationOption,
)


def render_leg_wb_inputs(
    *,
    leg_uids: list[str],
    stations: tuple[StationOption, ...],
    aircraft_profile_id: str,
    revision_id: str,
) -> tuple[dict, dict[str, str]]:
    """Collect crew and fuel inputs without inventing defaults.

    Returns:
        Valid leg conditions keyed by stable leg UID.
        Input errors keyed by stable leg UID.
    """

    crew_stations = [station for station in stations if station.category == "crew"]

    fuel_stations = [
        station for station in stations if station.category == "usable_fuel"
    ]

    st.markdown("**Crew & Fuel Loading**")

    st.caption(
        "Enter the actual planned loading quantities. "
        "Fuel values are in kilograms and are not yet linked "
        "to the demonstration fuel planner."
    )

    if not crew_stations:
        st.warning(
            "No crew loading stations are configured for this aircraft revision."
        )
        return {}, {uid: "No configured crew station." for uid in leg_uids}

    if not fuel_stations:
        st.warning(
            "No usable-fuel loading stations are configured for this aircraft revision."
        )
        return {}, {uid: "No configured usable-fuel station." for uid in leg_uids}

    prefix = f"wb_{aircraft_profile_id}_{revision_id}"

    crew_a, crew_b = st.columns(
        [1, 2],
        vertical_alignment="bottom",
    )

    pilots = {
        pilot_id: pilot for pilot_id, pilot in load_pilots().items() if pilot.active
    }

    with crew_a:
        selected_pilot_id = st.selectbox(
            "Pilot",
            options=["", *pilots],
            format_func=lambda pilot_id: (
                pilots[pilot_id].full_name if pilot_id else "Select pilot"
            ),
            key=f"{prefix}_selected_pilot",
        )

        if selected_pilot_id:
            selected_pilot = pilots[selected_pilot_id]

            pilot_weight = selected_pilot.weight_kg

            st.caption(f"Weight: {pilot_weight:.1f} kg")

            st.caption(f"Licence: {selected_pilot.licence_type}")

            st.caption(f"Medical: {selected_pilot.medical_status()}")

        else:
            pilot_weight = None

    crew_lookup = {station.station_id: station for station in crew_stations}

    with crew_b:
        pilot_station = st.selectbox(
            "Pilot loading station",
            options=["", *crew_lookup],
            format_func=lambda station_id: (
                crew_lookup[station_id].name if station_id else "Select crew station"
            ),
            key=f"{prefix}_pilot_station",
        )

    if len(crew_stations) > 1:
        st.caption(
            "Only one crew member is modelled in this "
            "development interface. Confirm that any "
            "additional required crew loads are included "
            "before operational use."
        )

    st.markdown("**Fuel by Flight Leg**")

    st.caption(
        "Takeoff and landing quantities represent total "
        "usable fuel at each configured station."
    )

    valid_conditions = {}
    errors = {}

    for index, uid in enumerate(leg_uids, start=1):
        with st.container(border=True):
            st.markdown(f"**LEG-{index:03d}**")

            takeoff_fuel = {}
            landing_fuel = {}

            for station in fuel_stations:
                st.caption(station.name)

                departure_col, arrival_col = st.columns(2)

                with departure_col:
                    takeoff_fuel[station.station_id] = st.number_input(
                        "Takeoff fuel (kg)",
                        min_value=0.0,
                        value=None,
                        step=1.0,
                        format="%.1f",
                        key=(f"{prefix}_{uid}_{station.station_id}_takeoff"),
                        placeholder="Enter fuel",
                    )

                with arrival_col:
                    landing_fuel[station.station_id] = st.number_input(
                        "Landing fuel (kg)",
                        min_value=0.0,
                        value=None,
                        step=1.0,
                        format="%.1f",
                        key=(f"{prefix}_{uid}_{station.station_id}_landing"),
                        placeholder="Enter fuel",
                    )

            try:
                valid_conditions[uid] = build_leg_conditions(
                    leg_uid=uid,
                    pilot_weight_kg=pilot_weight,
                    pilot_station_id=pilot_station,
                    takeoff_fuel=takeoff_fuel,
                    landing_fuel=landing_fuel,
                )

            except (
                LoadingInputError,
                LegConditionError,
            ) as error:
                errors[uid] = str(error)

    return valid_conditions, errors
