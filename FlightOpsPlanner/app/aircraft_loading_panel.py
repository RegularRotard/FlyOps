"""Connect the active aircraft, manifests and loading-station UI."""

from pathlib import Path

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.leg_wb_inputs import render_leg_wb_inputs
from app.loading_station_ui import render_loading_station_ui
from app.manifest_assignments import build_leg_manifests
from app.manifest_ui import (
    ASSIGNMENT_STATE,
    BAGGAGE_STATE,
    PASSENGER_STATE,
)
from flightops.database.models import (
    AircraftProfile,
    AircraftProfileRevision,
)
from flightops.operations.loading.leg_conditions import LegConditionError
from flightops.operations.loading.leg_wb_service import (
    calculate_leg_wb_conditions,
)
from flightops.operations.loading.manifest_adapter import (
    ManifestLoadingError,
)
from flightops.operations.loading.revision_bridge import (
    LoadingIntegrationError,
    calculate_partial_leg_wb,
    get_revision_loading_stations,
)
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
)

DATABASE_PATH = Path("data/databases/flightops.db")


def _load_aircraft_revision(
    aircraft_id: str,
    revision_id: str,
):
    """Read an aircraft and its exact configuration revision."""

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Aircraft database not found: {DATABASE_PATH}")

    # Use a read-only SQLite connection.

    engine = create_engine(
        "sqlite:///file:" + str(DATABASE_PATH.resolve()) + "?mode=ro&uri=true",
        connect_args={"uri": True},
    )

    try:
        with Session(engine) as session:
            aircraft = session.get(
                AircraftProfile,
                aircraft_id,
            )

            revision = session.get(
                AircraftProfileRevision,
                revision_id,
            )

            if aircraft is None:
                raise LoadingIntegrationError(
                    "Selected aircraft profile was not found."
                )

            if revision is None:
                raise LoadingIntegrationError(
                    "Selected configuration revision was not found."
                )

            if revision.profile_id != aircraft.id:
                raise LoadingIntegrationError(
                    "Selected revision belongs to a different aircraft."
                )

            session.expunge(aircraft)
            session.expunge(revision)

            return aircraft, revision

    finally:
        engine.dispose()


def render_aircraft_loading_panel(
    selected_aircraft,
    selected_revision,
) -> None:
    """Display loading assignments and partial per-leg W&B."""

    st.subheader("Aircraft Loading")

    if selected_aircraft is None or selected_revision is None:
        st.info(
            "Select an aircraft and configuration revision to assign loading stations."
        )
        return

    try:
        aircraft, revision = _load_aircraft_revision(
            selected_aircraft.aircraft_id,
            selected_revision.revision_id,
        )

        stations = get_revision_loading_stations(revision)

    except (
        FileNotFoundError,
        LoadingIntegrationError,
        ConfigurationAdapterError,
    ) as error:
        st.warning(str(error))
        return

    if not stations:
        st.warning("The selected configuration has no loading stations.")
        return

    legs = st.session_state.get(
        "flyops_leg_editor_rows",
        [],
    )

    assignments = st.session_state.get(
        ASSIGNMENT_STATE,
        {},
    )

    passengers = st.session_state.get(
        PASSENGER_STATE,
        {},
    )

    baggage = st.session_state.get(
        BAGGAGE_STATE,
        {},
    )

    uids = [leg["_uid"] for leg in legs]

    if not uids:
        st.info("Add flight legs before assigning aircraft loads.")
        return

    manifests = build_leg_manifests(
        assignments,
        uids,
    )

    st.caption(
        f"{aircraft.registration} · Configuration revision {revision.revision_number}"
    )

    leg_stations = render_loading_station_ui(
        manifests=manifests,
        passengers=passengers,
        baggage=baggage,
        stations=stations,
        aircraft_profile_id=aircraft.id,
        revision_id=revision.id,
    )

    st.divider()

    leg_conditions, condition_errors = render_leg_wb_inputs(
        leg_uids=uids,
        stations=stations,
        aircraft_profile_id=aircraft.id,
        revision_id=revision.id,
    )

    st.markdown("**Takeoff & Landing W&B**")

    st.caption(
        "Planning assessments using entered crew, payload and "
        "fuel quantities. These results do not authorize dispatch."
    )

    for index, manifest in enumerate(manifests, start=1):
        uid = manifest.leg_uid

        if uid in condition_errors:
            st.info(f"LEG-{index:03d}: {condition_errors[uid]}")
            continue

        try:
            assessment = calculate_leg_wb_conditions(
                manifest=manifest,
                station_assignments=leg_stations[uid],
                passengers=passengers,
                baggage=baggage,
                conditions=leg_conditions[uid],
                revision=revision,
                aircraft=aircraft,
            )

        except (
            ManifestLoadingError,
            LoadingIntegrationError,
            ConfigurationAdapterError,
            LegConditionError,
        ) as error:
            st.warning(f"LEG-{index:03d}: {error}")
            continue

        takeoff = assessment.takeoff
        landing = assessment.landing

        takeoff_calc = takeoff.calculation.calculation
        landing_calc = landing.calculation.calculation

        st.markdown(f"**LEG-{index:03d}**")

        columns = st.columns(4)

        columns[0].metric(
            "Takeoff weight",
            f"{takeoff_calc.total_weight_kg:.1f} kg",
        )

        columns[1].metric(
            "Takeoff CG",
            f"{takeoff_calc.cg_mm:.1f} mm",
        )

        columns[2].metric(
            "Landing weight",
            f"{landing_calc.total_weight_kg:.1f} kg",
        )

        columns[3].metric(
            "Landing CG",
            f"{landing_calc.cg_mm:.1f} mm",
        )

        st.caption(
            "Configured checks — "
            f"Takeoff: {takeoff.validation.status.value} | "
            f"Landing: {landing.validation.status.value}"
        )

        if not (takeoff.development_passed and landing.development_passed):
            st.warning(
                f"LEG-{index:03d}: One or more configured "
                "W&B checks did not pass. Review the "
                "validation results and aircraft limitations."
            )

    st.warning(
        "Development W&B assessment only. Crew completeness, "
        "fuel planning, reserves, tank distribution and "
        "other aircraft-specific requirements must still "
        "be reviewed. Not approved for flight release."
    )

    st.divider()

    st.markdown("**Partial Weight & Balance**")

    st.caption(
        "Includes aircraft basic empty weight and assigned "
        "manifest payload. Crew, fuel and other operational "
        "loads are not yet included."
    )

    for index, manifest in enumerate(manifests, start=1):
        try:
            result = calculate_partial_leg_wb(
                manifest=manifest,
                station_assignments=leg_stations[manifest.leg_uid],
                passengers=passengers,
                baggage=baggage,
                revision=revision,
                aircraft=aircraft,
            )

        except (
            ManifestLoadingError,
            LoadingIntegrationError,
            ConfigurationAdapterError,
        ) as error:
            st.warning(f"LEG-{index:03d}: {error}")
            continue

        columns = st.columns([1, 1, 1])

        columns[0].markdown(f"**LEG-{index:03d}**")

        columns[1].metric(
            "Partial weight",
            f"{result.total_weight_kg:.1f} kg",
        )

        columns[2].metric(
            "Partial CG",
            f"{result.cg_mm:.1f} mm",
        )

    st.warning(
        "Partial W&B only. These results do not establish "
        "takeoff or landing weight-and-balance compliance."
    )
