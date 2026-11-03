# FlyOps — Locations & basic map (Phase 5.4A–B)

This package adds `map_locations` and its indexes to the **existing** database.
It does not modify the existing aircraft or flight tables. Importing twice
will not overwrite existing saved locations. It uses the 22 airport and 10
waypoint source records previously provided.

## Install in WSL

```bash
cd ~/Projects/FlyOps/FlightOpsPlanner
source .venv/bin/activate
# Unzip this package into the current project root (preserving folders).
# Copy the zip from Windows Downloads or WSL filesystem first.
python -m pip install folium streamlit-folium
mkdir -p data/seed
# DB must already exist: data/databases/flightops.db
# Backup prior to adding the new table:
cp data/databases/flightops.db data/databases/flightops.db.before-locations
python scripts/import_locations.py
ruff check app/ src/flightops/locations/ tests/locations/
python -m pytest tests/locations/ -q
python -m pytest tests/ -q
```

## Wire up the new page (two edits to app/main.py)

1. Add at the top:

```python
from app.location_manager import render_location_manager
```

2. In the sidebar's `st.radio` navigation **options list**, insert
`"Locations & Map"` (after `"Flight Planning"` is suggested).

3. In the main page `if/elif` chain (the same indentation as `elif page == "Aircraft":`),
insert **before that existing Aircraft branch**:

```python
elif page == "Locations & Map":
    render_location_manager()
```

Run `python run_flyops.py` and open http://127.0.0.1:8501.

## Features

- Search saved records by name/ID; filter by category.
- Distinct markers for airports, landing zones, refuelling, and waypoints.
- Click map to use a point temporarily or save it as an **unverified** point.
- Source evidence retained for all imported records in details_json.
- **Internet required for OSM map imagery**. Offline checkbox disables map tiles;
  points still work, but land/coast outlines disappear. Full offline basemap
  is a separate next phase; do not bulk-download OSM standard tiles.
- "Use for this plan only" stores the click in session state; connecting it to
  flight-leg selection is planned but **not implemented here**.
- Neither an imported airport nor a manually added landing/refuelling point is
  an approval of aviation suitability, fuel availability or active frequencies.

## Source integrity

Original source PDFs were generated July 2026 and marked valid until
2026-10-01. Their coordinates are transcribed for demonstration only.
Revalidate source currency before operational use.
