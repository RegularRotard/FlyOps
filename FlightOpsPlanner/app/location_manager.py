"""Basic, staff-friendly saved-location map (not an aviation chart)."""

from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

from flightops.locations.catalog import CATEGORIES, add_location, list_locations

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "databases" / "flightops.db"

MARKERS = {
    "Airport": ("blue", "plane"),
    "Landing Zone": ("green", "home"),
    "Refuelling Point": ("orange", "tint"),
    "Waypoint": ("purple", "map-marker"),
}


def render_location_manager() -> None:
    """Render searchable map and save-on-click form."""
    st.title("Locations & Map")
    st.caption("Airport • Landing Zone • Refuelling Point • Waypoint")
    st.warning(
        "Imported airport plates expired on 1 October 2026. "
        "These locations are for demonstration and planning only. "
        "A saved landing zone or refuelling point is not automatically approved or available."
    )

    search_col, category_col = st.columns([2, 3])
    with search_col:
        query = st.text_input(
            "Search by name or location ID", placeholder="e.g. HTZA, Zanzibar"
        )
    with category_col:
        categories = st.multiselect(
            "Show categories", CATEGORIES, default=list(CATEGORIES)
        )
    try:
        locations = list_locations(DB_PATH, search=query, categories=tuple(categories))
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.error(f"Location catalogue unavailable: {exc}")
        return

    st.caption(f"{len(locations)} matching saved locations")
    if locations:
        options = {f"{loc.name} - {loc.location_id}": loc for loc in locations}
        selected_name = st.selectbox("Jump to saved location", ["Overview", *options])
    else:
        options = {}
        selected_name = "Overview"

    # Public OSM tile servers require internet and are NOT an offline tile cache.
    offline = st.checkbox(
        "Offline mode (no basemap tiles)",
        value=False,
        help="Markers and coordinates still work without internet, but geographical imagery "
        "requires locally installed map tiles, which will be added in a later stage.",
    )

    selected = options.get(selected_name)
    centre = [selected.latitude, selected.longitude] if selected else [-6.2, 36.0]
    zoom = 11 if selected else 6
    map_object = folium.Map(
        location=centre,
        zoom_start=zoom,
        tiles=None if offline else "OpenStreetMap",
        control_scale=True,
    )

    for loc in locations:
        icon_color, icon_name = MARKERS.get(loc.category, ("gray", "info-sign"))
        # Folium escapes/sanitizes text used as tooltips.
        tooltip = f"{loc.name} ({loc.location_id}) — {loc.category}"
        folium.Marker(
            location=[loc.latitude, loc.longitude],
            tooltip=tooltip,
            icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            popup=folium.Popup(
                folium.IFrame(
                    html=(
                        f"<b>{_escape(loc.name)}</b><br>"
                        f"{_escape(loc.category)}<br>"
                        f"{loc.latitude:.6f}, {loc.longitude:.6f}<br>"
                        f"{_escape(loc.verification_status)}"
                    ),
                    width=260,
                    height=130,
                ),
                max_width=300,
            ),
        ).add_to(map_object)

    map_result = st_folium(
        map_object,
        height=520,
        width=None,
        returned_objects=["last_clicked"],
        key="flyops_location_map",
    )

    clicked = map_result.get("last_clicked") if map_result else None
    if clicked and "lat" in clicked and "lng" in clicked:
        click_id = (clicked["lat"], clicked["lng"])
        if st.session_state.get("flyops_last_map_click") != click_id:
            st.session_state["flyops_last_map_click"] = click_id
            st.session_state["flyops_pending_location"] = click_id

    pending = st.session_state.get("flyops_pending_location")
    if pending is not None:
        latitude, longitude = pending
        st.subheader("📍 Location selected")
        st.write(f"Coordinates: **{latitude:.6f}, {longitude:.6f}**")
        choice = st.radio(
            "What would you like to do?",
            ["Use for this plan only", "Save to location database"],
            horizontal=True,
        )
        if choice == "Use for this plan only":
            if st.button("Use selected point", type="primary"):
                st.session_state["flyops_temporary_location"] = pending
                st.session_state.pop("flyops_pending_location", None)
                st.success(
                    "Temporary point selected. Flight-leg integration comes next."
                )
        else:
            with st.form("save_map_location", clear_on_submit=False):
                name = st.text_input("Location name")
                category = st.selectbox("Category", CATEGORIES[1:])
                notes = st.text_area("Notes (optional)")
                submitted = st.form_submit_button("Save location", type="primary")
            if submitted:
                try:
                    new_id = add_location(
                        DB_PATH,
                        name=name,
                        category=category,
                        latitude=latitude,
                        longitude=longitude,
                        notes=notes,
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop("flyops_pending_location", None)
                    st.success(f"Saved {name!r} as {new_id} (Unverified)")
                    st.rerun()
        if st.button("Cancel selected point"):
            st.session_state.pop("flyops_pending_location", None)
            st.rerun()

    if selected:
        st.divider()
        st.subheader(f"{selected.name} — {selected.location_id}")
        st.write(
            f"**Category:** {selected.category} | **Status:** {selected.verification_status}"
        )
        st.write(f"**Coordinates:** {selected.latitude:.6f}, {selected.longitude:.6f}")
        if selected.source_document:
            st.write(f"**Source:** {selected.source_document}")
        if selected.source_valid_until:
            st.write(f"**Source valid until:** {selected.source_valid_until}")
        if selected.details:
            with st.expander("Imported source details"):
                st.json(selected.details)


def _escape(text: str) -> str:
    from html import escape

    return escape(str(text), quote=True)
