"""Staff-friendly estimate of route distance, ETI and ETA from saved points."""

from datetime import date, datetime, time
from pathlib import Path

import streamlit as st

from flightops.locations.catalog import list_locations
from flightops.locations.routing import estimate_route

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "databases" / "flightops.db"


def render_route_estimator() -> None:
    """Estimate a single flight using saved airport/LZ/waypoint coordinates."""
    st.divider()
    st.subheader("Flight distance and time estimator")
    st.caption(
        "Select saved locations. This works without map tiles or internet access. "
        "Planning speeds are entered manually until aircraft profiles are connected."
    )
    try:
        locations = list_locations(DB_PATH)
    except (FileNotFoundError, OSError, ValueError) as exc:
        st.error(f"Location database unavailable: {exc}")
        return

    if len(locations) < 2:
        st.info("Import or save at least two locations to estimate a route.")
        return

    by_id = {location.location_id: location for location in locations}
    ids = tuple(by_id)

    def display(location_id: str) -> str:
        location = by_id[location_id]
        return f"{location.name} ({location_id}) · {location.category}"

    departure_id = st.selectbox(
        "Departure", ids, format_func=display, key="route_est_departure"
    )
    destination_id = st.selectbox(
        "Destination",
        ids,
        format_func=display,
        index=1,
        key="route_est_destination",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        etd_date = st.date_input("Departure date", date.today(), key="route_est_date")
    with col2:
        etd_time = st.time_input("ETD (local)", time(8, 0), key="route_est_time")
    with col3:
        speed = st.number_input(
            "Planned groundspeed (kt)",
            min_value=1.0,
            value=100.0,
            step=5.0,
            help="Fictional 100-kt starting value. Enter a suitable "
            "approved planning assumption for the selected aircraft.",
            key="route_est_speed",
        )

    if st.button("Calculate route estimate", type="primary", key="route_est_calculate"):
        departure = by_id[departure_id]
        destination = by_id[destination_id]
        try:
            result = estimate_route(
                (
                    (departure.latitude, departure.longitude),
                    (destination.latitude, destination.longitude),
                ),
                speed,
                datetime.combine(etd_date, etd_time),
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            d, t, a = st.columns(3)
            d.metric("Straight-line distance", f"{result.distance_nm:.1f} NM")
            t.metric("Estimated flight time (ETI)", f"{result.estimated_minutes} min")
            a.metric("Estimated arrival (ETA)", result.eta.strftime("%d %b %H:%M"))
            st.caption(
                "ETI is rounded up to a whole minute. Direct-line estimate only; "
                "no routing, wind, climb, descent or operational constraints included. "
                "ETD and ETA use the entered local date/time."
            )
