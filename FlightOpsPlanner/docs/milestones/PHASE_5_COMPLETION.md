# FlyOps — Phase 5 Completion

## Phase
Flight Planning, Mapping and Scheduling

## Objective
Develop an interactive, multi-leg helicopter flight-planning
interface suitable for operators working in Tanzania and Zanzibar.

## Implemented Features

### Flight-leg management
- Multiple flight legs.
- Automatic sequential leg numbering.
- Charter, Ferry and Scenic flight types.
- Add, edit, duplicate, remove and reorder flight legs.
- Route continuity between consecutive legs.
- Compact flight-leg overview.

### Location management
- SQLite-backed location catalogue.
- Searchable departure and destination selectors.
- Airports, landing zones, refuelling points and waypoints.
- Custom location creation.
- Manual coordinate entry.
- Map-based coordinate selection.

### Mapping
- Visual route display.
- Flight-leg mapping.
- Scenic operating-radius visualization.
- Route-distance-based flight duration estimates.
- Calculations independent of online map tiles.

### Scheduling
- Automatic ETI calculation.
- Manual ETI overrides and review indicators.
- Automatic ETA calculation.
- Automatic ETD calculation.
- Manual ETD overrides.
- Scheduling conflict adjustment.
- ETD adjustment provenance.
- Sequential schedule recalculation.
- Midnight rollover handling.

### Flight-planning overview
- Route summary.
- ETD, ETI and ETA indicators.
- Automatic/manual status indicators.
- Planning warnings.
- Add, edit, duplicate and reorder controls.

## Limitations

- Planning groundspeed does not yet incorporate comprehensive
  aircraft performance or meteorological corrections.
- Straight-line route estimates do not establish terrain,
  obstacle, airspace or operational clearance.
- Offline basemap tile packaging remains outstanding.
- Passenger and baggage assignments are not yet integrated
  into the flight-leg planning interface.
- Per-leg aircraft weight and balance is not yet integrated
  with the passenger manifest.
- Fuel planning and fuel reconciliation require integration
  with the complete operational workflow.
- Generated operational records and regulatory documents
  require further development and validation.
- Planning status indicators do not constitute dispatch approval.

## Next Phase

Phase 6 — Passenger and Baggage Management

Core objectives:

1. Create passenger records.
2. Create baggage records.
3. Assign passengers to individual flight legs.
4. Track boarding and disembarkation.
5. Preserve passenger assignments when flight legs change.
6. Calculate passenger and baggage loads for each leg.
7. Prepare integration with aircraft weight-and-balance models.

## Verification

Completion is conditional on:

- Ruff lint passing.
- Ruff formatting checks passing.
- Complete pytest suite passing.
- Manual interface verification.
- Successful Git checkpoint.

## Status

Implementation complete; final verification required.
