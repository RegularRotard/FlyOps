"""Draw Scenic flight operating areas on Folium maps."""

import folium

from flightops.locations.scenic_radius import (
    calculate_scenic_radius,
    scenic_radius_metres,
)


def add_scenic_radius(
    map_object: folium.Map,
    *,
    latitude: float,
    longitude: float,
    duration_minutes: int,
    cruise_speed_knots: float,
    leg_id: str,
) -> None:
    """Add a theoretical Scenic operating-radius overlay."""

    radius_nm = calculate_scenic_radius(
        duration_minutes,
        cruise_speed_knots,
    )

    radius_m = scenic_radius_metres(
        duration_minutes,
        cruise_speed_knots,
    )

    colour = "#2563EB" if duration_minutes == 15 else "#9333EA"

    folium.Circle(
        location=[latitude, longitude],
        radius=radius_m,
        color=colour,
        weight=2,
        fill=True,
        fill_color=colour,
        fill_opacity=0.15,
        tooltip=(
            f"{leg_id}: {duration_minutes}-minute Scenic — {radius_nm:.1f} NM radius"
        ),
        popup=folium.Popup(
            f"<b>{leg_id} — Scenic</b><br>"
            f"Duration: {duration_minutes} minutes<br>"
            f"Planning speed: {cruise_speed_knots:.0f} kt<br>"
            f"Theoretical radius: {radius_nm:.1f} NM<br>"
            "Illustrative out-and-back reach; not a guaranteed "
            "operating area.",
            max_width=300,
        ),
    ).add_to(map_object)
