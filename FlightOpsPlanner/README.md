# FlyOps Phase 5.5 — Saved-location route estimator

This is an additive patch; it does not overwrite existing aircraft, database, location map or leg-editor code.

## Installation

1. Extract the ZIP at the **root of FlightOpsPlanner**, ensuring `app/route_estimator.py`, `src/flightops/locations/routing.py`, and `tests/locations/test_routing.py` land in those paths.
2. In `app/main.py`, add:

   `from app.route_estimator import render_route_estimator`

3. Find the branch:

   ```python
   elif page == "Locations & Map":
       render_location_manager()
   ```

   Change it to:

   ```python
   elif page == "Locations & Map":
       render_location_manager()
       render_route_estimator()
   ```

4. Verify dependencies, import and run:

   ```bash
   cd ~/Projects/FlyOps/FlightOpsPlanner
   source .venv/bin/activate
   ruff check app/ src/flightops/ tests/ --fix
   ruff format app/ src/flightops/ tests/
   ruff check app/ src/flightops/ tests/
   python -m pytest tests/locations/test_routing.py -v
   python -m pytest tests/ -q
   python run_flyops.py
   ```

5. Open **Locations & Map**, scroll to **Flight distance and time estimator**. Choose e.g. HTZA and HTDA, enter planned groundspeed and ETD, and click Calculate route estimate.

## Limits

- Distance uses haversine/geographic great-circle approximation, not actual route flown.
- ETI uses user-entered planned **groundspeed** and rounds up to next minute.
- Scenic returning to departure must use the existing fixed 15/30-minute blocks or a saved multi-point route.
- No aircraft suitability, wind, performance, reserves, fuel quantity, or navigation approval is inferred.
- Only saved coordinate data is required. No network, map service, or online tiles needed for the calculation.
- This separate route estimator **does not yet automatically populate flight-leg ETI**. That link should be built after checking the installed leg-editor code so we don't overwrite recent route/time constraints.
