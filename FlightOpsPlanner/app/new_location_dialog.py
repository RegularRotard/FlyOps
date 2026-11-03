"""Create saved locations directly from the flight-leg editor."""

from html import escape
from math import isfinite
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

from flightops.locations.catalog import (
    CATEGORIES,
    add_location,
    list_locations,
)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "databases" / "flightops.db"

PENDING_SELECTION_KEY = "flyops_new_location_selection"

# Airport records should come from the airport data import workflow.
CREATABLE_CATEGORIES = tuple(
    category for category in CATEGORIES if category != "Airport"
)


def valid_coordinates(latitude: float, longitude: float) -> bool:
    """Validate geographical coordinates."""

    return (
        isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def parse_decimal_coordinates(
    latitude_text: str,
    longitude_text: str,
) -> tuple[float, float]:
    """Parse and validate decimal-degree coordinates."""

    try:
        latitude = float(latitude_text.strip())
        longitude = float(longitude_text.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter valid decimal latitude and longitude.") from exc

    if not valid_coordinates(latitude, longitude):
        raise ValueError(
            "Latitude must be between -90 and 90; "
            "longitude must be between -180 and 180."
        )

    return latitude, longitude


def save_new_location(
    *,
    name: str,
    category: str,
    latitude: float,
    longitude: float,
    notes: str = "",
    db_path: Path = DB_PATH,
) -> str:
    """Validate and save a new location to the shared catalogue."""

    name = name.strip()

    if not name:
        raise ValueError("Enter a location name.")

    if category not in CREATABLE_CATEGORIES:
        raise ValueError("Select a supported location category.")

    if not valid_coordinates(latitude, longitude):
        raise ValueError("Invalid latitude or longitude.")

    return add_location(
        db_path,
        name=name,
        category=category,
        latitude=latitude,
        longitude=longitude,
        notes=notes.strip(),
    )


@st.dialog("➕ New Location", width="large")
def new_location_dialog(uid: str, field: str) -> None:
    """Select a map point, name it, save it and assign it to a leg."""

    if field not in ("Departure", "Destination"):
        st.error("Invalid flight-leg location field.")
        return

    st.caption(
        f"Creating a new {field.lower()} location. "
        "Click the map to select its coordinates."
    )

    st.warning(
        "New locations are saved as unverified. "
        "A saved location is not automatically an approved landing site."
    )

    point_key = f"new_location_point_{uid}_{field}"
    map_key = f"new_location_map_{uid}_{field}"

    selected_point = st.session_state.get(point_key)

    offline = st.checkbox(
        "Offline mode (no background map tiles)",
        key=f"new_location_offline_{uid}_{field}",
        help=(
            "Map selection still works using coordinates. "
            "Background imagery requires internet until local tiles "
            "are implemented."
        ),
    )

    if selected_point is not None:
        centre = list(selected_point)
        zoom = 12
    else:
        centre = [-6.22, 39.22]
        zoom = 9

    map_object = folium.Map(
        location=centre,
        zoom_start=zoom,
        tiles=None if offline else "OpenStreetMap",
        control_scale=True,
    )

    # Show existing saved points as references.
    try:
        saved_locations = list_locations(DB_PATH)
    except (OSError, ValueError) as exc:
        st.warning(f"Existing locations unavailable: {exc}")
        saved_locations = ()

    for location in saved_locations:
        folium.CircleMarker(
            location=[
                location.latitude,
                location.longitude,
            ],
            radius=4,
            color="#64748B",
            fill=True,
            fill_opacity=0.8,
            tooltip=(f"{escape(location.name)} ({escape(location.location_id)})"),
        ).add_to(map_object)

    if selected_point is not None:
        folium.Marker(
            location=list(selected_point),
            tooltip="New location",
            icon=folium.Icon(
                color="green",
                icon="map-marker",
            ),
        ).add_to(map_object)

    map_result = st_folium(
        map_object,
        height=380,
        width=None,
        key=map_key,
        returned_objects=["last_clicked"],
    )

    clicked = map_result.get("last_clicked") if map_result else None

    if clicked and "lat" in clicked and "lng" in clicked:
        clicked_point = (
            float(clicked["lat"]),
            float(clicked["lng"]),
        )

        if valid_coordinates(*clicked_point):
            selected_point = clicked_point
            st.session_state[point_key] = clicked_point

    if selected_point is None:
        st.info("📍 Click the map to choose a location.")
    else:
        latitude, longitude = selected_point

        st.success(f"Selected coordinates: {latitude:.6f}, {longitude:.6f}")

    latitude_key = f"new_location_latitude_{uid}_{field}"
    longitude_key = f"new_location_longitude_{uid}_{field}"
    synced_point_key = f"new_location_synced_point_{uid}_{field}"

    if (
        selected_point is not None
        and st.session_state.get(synced_point_key) != selected_point
    ):
        latitude, longitude = selected_point

        st.session_state[latitude_key] = f"{latitude:.6f}"
        st.session_state[longitude_key] = f"{longitude:.6f}"
        st.session_state[synced_point_key] = selected_point

    with st.form(
        f"new_location_form_{uid}_{field}",
        clear_on_submit=False,
    ):
        coordinate_col1, coordinate_col2 = st.columns(2)

        with coordinate_col1:
            latitude_text = st.text_input(
                "Latitude (decimal degrees) *",
                key=latitude_key,
                placeholder="-6.221944",
                help="South latitudes are negative.",
            )

        with coordinate_col2:
            longitude_text = st.text_input(
                "Longitude (decimal degrees) *",
                key=longitude_key,
                placeholder="39.224444",
                help="West longitudes are negative.",
            )

        st.caption(
            "Click the map to populate these fields automatically, "
            "or enter coordinates manually."
        )

        name = st.text_input(
            "Location name *",
            placeholder="e.g. North Coast Landing Zone",
        )

        category = st.selectbox(
            "Location category *",
            options=CREATABLE_CATEGORIES,
        )

        notes = st.text_area(
            "Notes",
            placeholder=(
                "Optional description, access information "
                "or operational considerations."
            ),
        )

        submitted = st.form_submit_button(
            "💾 Save & Select",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            latitude, longitude = parse_decimal_coordinates(
                latitude_text,
                longitude_text,
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        try:
            location_id = save_new_location(
                name=name,
                category=category,
                latitude=latitude,
                longitude=longitude,
                notes=notes,
            )
        except (ValueError, OSError) as exc:
            st.error(f"Unable to save location: {exc}")
            return

        # The flight editor applies this on the next full app rerun,
        # before its location widgets are instantiated.
        st.session_state[PENDING_SELECTION_KEY] = {
            "uid": uid,
            "field": field,
            "location_id": location_id,
        }

        st.session_state.pop(point_key, None)

        st.rerun()
