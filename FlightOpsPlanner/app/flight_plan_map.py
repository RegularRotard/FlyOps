"""Display flight routes and Scenic operating radii in FlyOps."""

from datetime import datetime
from html import escape
from math import isfinite
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.scenic_map import add_scenic_radius
from flightops.locations.catalog import list_locations
from flightops.locations.routing import distance_nm

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "databases" / "flightops.db"

ROUTE_COLOURS = {
    "Charter": "#16A34A",
    "Ferry": "#EA580C",
}


def _format_time(value: object) -> str:
    """Format a stored flight-plan datetime for display."""

    if value is None or pd.isna(value):
        return "Not set"

    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _route_popup(
    leg_id: str,
    flight_type: str,
    distance: float,
    eti_minutes: float,
    etd: str,
    eta: str,
) -> str:
    """Build an escaped route-information popup."""

    return (
        f"<b>{escape(leg_id)} — {escape(flight_type)}</b><br>"
        f"Distance: {distance:.1f} NM<br>"
        f"Planned ETI: {eti_minutes:.0f} min<br>"
        f"ETD: {escape(etd)}<br>"
        f"ETA: {escape(eta)}<br>"
        "<small>Direct-route planning estimate</small>"
    )


def build_flight_plan_map(
    legs: pd.DataFrame,
    locations: dict,
    cruise_speed_knots: float,
    *,
    offline: bool = False,
) -> tuple[folium.Map, list[str]]:
    """Build route and Scenic overlays using saved coordinates.

    Returns the map and warnings for unresolved locations.
    """

    if not isfinite(cruise_speed_knots) or cruise_speed_knots <= 0:
        raise ValueError("Cruise speed must be positive and finite.")

    map_object = folium.Map(
        location=[-6.2, 36.0],
        zoom_start=6,
        tiles=None if offline else "OpenStreetMap",
        control_scale=True,
    )

    bounds = []
    warnings = []

    for _, row in legs.iterrows():
        leg_id = str(row["Leg"])
        flight_type = str(row["Flight Type"])
        departure_id = str(row["Departure"]).strip()
        destination_id = str(row["Destination"]).strip()

        departure = locations.get(departure_id)
        destination = locations.get(destination_id)

        if departure is None:
            warnings.append(
                f"{leg_id}: Departure {departure_id!r} "
                "is not in the saved-location database."
            )
            continue

        start = [
            departure.latitude,
            departure.longitude,
        ]

        bounds.append(start)

        eti_minutes = float(row["Flight Minutes"])

        etd = (f"{row.get('ETD Date', '')} {row.get('ETD Time', '')}").strip()

        eta = _format_time(row.get("ETA"))

        if flight_type == "Scenic":
            if eti_minutes not in (15.0, 30.0):
                warnings.append(f"{leg_id}: Scenic duration must be 15 or 30 minutes.")
                continue

            if departure_id != destination_id:
                warnings.append(f"{leg_id}: Scenic departure and destination differ.")
                continue

            add_scenic_radius(
                map_object,
                latitude=departure.latitude,
                longitude=departure.longitude,
                duration_minutes=int(eti_minutes),
                cruise_speed_knots=cruise_speed_knots,
                leg_id=leg_id,
            )

            folium.Marker(
                location=start,
                tooltip=f"{leg_id}: Scenic departure and return",
                popup=folium.Popup(
                    (
                        f"<b>{escape(leg_id)}</b><br>"
                        f"{escape(departure.name)}<br>"
                        f"ETD: {escape(etd)}<br>"
                        f"ETA: {escape(eta)}"
                    ),
                    max_width=300,
                ),
                icon=folium.Icon(
                    color="blue",
                    icon="plane",
                    prefix="fa",
                ),
            ).add_to(map_object)

            continue

        if destination is None:
            warnings.append(
                f"{leg_id}: Destination {destination_id!r} "
                "is not in the saved-location database."
            )
            continue

        end = [
            destination.latitude,
            destination.longitude,
        ]

        bounds.append(end)

        distance = distance_nm(
            departure.latitude,
            departure.longitude,
            destination.latitude,
            destination.longitude,
        )

        colour = ROUTE_COLOURS.get(
            flight_type,
            "#64748B",
        )

        popup = _route_popup(
            leg_id,
            flight_type,
            distance,
            eti_minutes,
            etd,
            eta,
        )

        folium.PolyLine(
            locations=[start, end],
            color=colour,
            weight=4,
            opacity=0.85,
            tooltip=(f"{leg_id}: {distance:.1f} NM — ETI {eti_minutes:.0f} min"),
            popup=folium.Popup(
                popup,
                max_width=320,
            ),
        ).add_to(map_object)

        folium.CircleMarker(
            location=start,
            radius=5,
            color=colour,
            fill=True,
            fill_opacity=1,
            tooltip=f"{leg_id} departure: {departure_id}",
        ).add_to(map_object)

        folium.CircleMarker(
            location=end,
            radius=5,
            color=colour,
            fill=True,
            fill_opacity=1,
            tooltip=f"{leg_id} destination: {destination_id}",
        ).add_to(map_object)

    if len(bounds) == 1:
        map_object.location = bounds[0]
        map_object.options["zoom"] = 10

    elif len(bounds) > 1:
        map_object.fit_bounds(bounds)

    return map_object, warnings


def render_flight_plan_map(legs: pd.DataFrame) -> None:
    """Render the flight-plan map beneath the flight-leg editor."""

    st.subheader("Flight Plan Map")

    st.caption("Visual overview of scheduled flights and Scenic operating areas.")

    if legs.empty:
        st.info("Add a flight leg to display its route.")
        return

    speed_col, offline_col = st.columns([2, 1])

    with speed_col:
        cruise_speed = st.number_input(
            "Planning Cruise Speed (kt)",
            min_value=1.0,
            max_value=300.0,
            value=100.0,
            step=5.0,
            key="flyops_map_cruise_speed",
            help=(
                "Demonstration planning speed. "
                "Aircraft-profile integration will follow."
            ),
        )

    with offline_col:
        offline = st.checkbox(
            "No online map tiles",
            value=False,
            key="flyops_flight_map_offline",
            help=(
                "Displays routes and markers without geographical background imagery."
            ),
        )

    try:
        saved_locations = list_locations(DB_PATH)

        location_lookup = {
            location.location_id: location for location in saved_locations
        }

        map_object, warnings = build_flight_plan_map(
            legs,
            location_lookup,
            cruise_speed,
            offline=offline,
        )

    except (FileNotFoundError, OSError, ValueError) as exc:
        st.error(f"Flight-plan map unavailable: {exc}")
        return

    st_folium(
        map_object,
        height=480,
        width=None,
        returned_objects=[],
        key="flyops_flight_plan_map",
    )

    st.caption(
        "🔵 15-minute Scenic radius  |  "
        "🟣 30-minute Scenic radius  |  "
        "🟢 Charter route  |  "
        "🟠 Ferry route"
    )

    st.caption(
        "Scenic circles represent theoretical out-and-back reach "
        "at the selected planning speed. Route lines show direct "
        "connections, not confirmed flight tracks."
    )

    for warning in warnings:
        st.warning(warning)
