"""FlyOps interactive flight-planning prototype.

Development application using fictional aircraft fuel data.

Not approved for operational flight planning or flight release.
"""

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app.aircraft_catalog import (
    list_aircraft,
    list_aircraft_revisions,
)
from app.flight_leg_editor import render_flight_leg_editor
from app.flight_plan_map import render_flight_plan_map
from app.location_manager import render_location_manager
from app.route_estimator import render_route_estimator
from flightops.fuel.configuration import (
    FuelConsumptionRate,
    FuelPhase,
    FuelPlanningConfiguration,
)
from flightops.fuel.display import FuelDisplayBasis, display_fuel
from flightops.fuel.standard_density import FuelGrade, fuel_density_kg_per_litre
from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    LegFuelState,
)
from flightops.operations.schemas.flight_planning import (
    FlightPlanningLeg,
    FlightType,
)
from flightops.operations.services.flight_day_fuel import (
    calculate_flight_day_fuel,
)


def format_fuel_quantity(
    kilograms: float,
    density: float,
    flight_consumption: float,
) -> str:
    """Display fuel in litres, flight-equivalent minutes and kilograms."""

    basis = FuelDisplayBasis(
        density_kg_per_litre=density,
        consumption_kg_per_hour=flight_consumption,
    )

    fuel = display_fuel(kilograms, basis)

    litres = f"{fuel.litres:.1f} L" if fuel.litres is not None else "N/A L"

    minutes = f"{fuel.minutes:.0f} min" if fuel.minutes is not None else "N/A min"

    return f"{litres} | {minutes} | {fuel.kilograms:.1f} kg"


st.set_page_config(
    page_title="FlyOps | Flight Operations Planner",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------
# Fictional development aircraft configuration
# ---------------------------------------------------------------------


def demo_aircraft_configuration():
    """Return fictional rates for interface development."""

    return FuelPlanningConfiguration(
        fuel_type="Fictional test fuel",
        default_density_kg_per_litre=0.8,
        density_source_document_id="DEMO-DENSITY",
        consumption_rates=[
            FuelConsumptionRate(
                phase=FuelPhase.FLIGHT,
                consumption_kg_per_hour=72.0,
                source_document_id="DEMO-FLIGHT",
            ),
            FuelConsumptionRate(
                phase=FuelPhase.IDLE,
                consumption_kg_per_hour=24.0,
                source_document_id="DEMO-IDLE",
            ),
        ],
    )


# ---------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------


def default_flight_legs():
    """Initial fictional flight schedule."""

    return pd.DataFrame(
        [
            {
                "Leg": "LEG-001",
                "Flight Type": "Scenic",
                "Departure": "HTZA",
                "Destination": "HTZA",
                "Flight Minutes": 15.0,
                "Additional Idle": 0.0,
                "Shutdown": False,
            },
            {
                "Leg": "LEG-002",
                "Flight Type": "Scenic",
                "Departure": "HTZA",
                "Destination": "HTZA",
                "Flight Minutes": 30.0,
                "Additional Idle": 0.0,
                "Shutdown": True,
            },
            {
                "Leg": "LEG-003",
                "Flight Type": "Charter",
                "Departure": "HTZA",
                "Destination": "HTDA",
                "Flight Minutes": 45.0,
                "Additional Idle": 0.0,
                "Shutdown": True,
            },
        ]
    )


if "flight_legs" not in st.session_state:
    st.session_state.flight_legs = default_flight_legs()
required_columns = set(default_flight_legs().columns)

if not required_columns.issubset(st.session_state.flight_legs.columns):
    st.session_state.flight_legs = default_flight_legs()

# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------


with st.sidebar:
    st.title("🚁 FlyOps")

    st.caption("Flight Operations Planner")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Flight Planning",
            "Locations & Map",
            "Aircraft",
            "Weight & Balance",
            "Reports",
        ],
    )

    st.divider()

    st.subheader("Aircraft Selection")

    try:
        aircraft_profiles = list_aircraft()

    except (FileNotFoundError, RuntimeError) as error:
        aircraft_profiles = ()
        st.error(str(error))

    selected_aircraft = None
    selected_revision = None

    if aircraft_profiles:
        aircraft_lookup = {
            aircraft.aircraft_id: aircraft for aircraft in aircraft_profiles
        }

        aircraft_ids = list(aircraft_lookup)

        selected_aircraft_id = st.selectbox(
            "Aircraft",
            options=aircraft_ids,
            format_func=lambda aircraft_id: aircraft_lookup[aircraft_id].registration,
        )

        selected_aircraft = aircraft_lookup[selected_aircraft_id]

        st.caption(f"Registration: {selected_aircraft.registration}")

        st.caption(f"Serial number: {selected_aircraft.serial_number}")

        st.caption(f"Variant ID: {selected_aircraft.variant_id}")

        try:
            revisions = list_aircraft_revisions(selected_aircraft.aircraft_id)

        except RuntimeError as error:
            revisions = ()
            st.error(str(error))

        if revisions:
            revision_lookup = {revision.revision_id: revision for revision in revisions}

            selected_revision_id = st.selectbox(
                "Configuration Revision",
                options=list(revision_lookup),
                format_func=lambda revision_id: (
                    f"Revision {revision_lookup[revision_id].revision_number}"
                ),
            )

            selected_revision = revision_lookup[selected_revision_id]

            st.caption(
                f"Configuration status: {selected_revision.configuration_status}"
            )

        else:
            st.warning("This aircraft has no saved configuration revisions.")

    else:
        st.info(
            "No saved aircraft profiles are available. "
            "The demonstration fuel planner can still be used."
        )

    st.divider()

    st.caption("Fuel calculations currently use fictional demo rates.")

    st.caption("Flight consumption: 72 kg/hour")
    st.caption("Idle consumption: 24 kg/hour")
    st.caption("Fuel density: 0.80 kg/L")

    st.divider()

    st.warning(
        "Development prototype only. Not approved for operational flight release."
    )


# ---------------------------------------------------------------------
# Flight Planning
# ---------------------------------------------------------------------


if page == "Flight Planning":
    st.title("Flight Planning")

    st.caption("Create and calculate multi-leg helicopter operations.")

    operation_id = st.text_input(
        "Operation Reference",
        value="DEMO-OP-001",
    )

    edited = render_flight_leg_editor(st.session_state.flight_legs)

    st.session_state.flight_legs = edited

    st.divider()
    render_flight_plan_map(edited)

    st.caption(
        "Scenic flights currently support 15- and 30-minute blocks. "
        "Ferry and Charter durations are entered manually."
    )

    st.divider()

    st.subheader("Fuel Planning")
    st.info(
        "DEMONSTRATION MODE — The fuel consumption rates and density "
        "below are fictional and are not taken from the selected "
        "aircraft configuration."
    )

    col1, col2 = st.columns(2)

    with col1:
        flight_rate_lph = st.number_input(
            "Flight Fuel Consumption (L/hour)",
            min_value=0.1,
            value=90.0,
            step=1.0,
        )

        idle_rate_lph = st.number_input(
            "Idle Fuel Consumption (L/hour)",
            min_value=0.1,
            value=30.0,
            step=1.0,
        )
    with col2:
        fuel_grade = st.selectbox(
            "Fuel type",
            options=list(FuelGrade),
            index=list(FuelGrade).index(FuelGrade.AVGAS),
            format_func=lambda grade: grade.value,
        )
        density = fuel_density_kg_per_litre(fuel_grade)
        st.caption(
            f"Reference density: {density:.3f} kg/L at 15°C (planning assumption)"
        )

        flight_rate = flight_rate_lph * density
        idle_rate = idle_rate_lph * density
        engine_running_at_start = st.checkbox(
            "Engine already running at start",
            value=False,
        )

    st.caption("Startup allowance: 6 minutes. Shutdown allowance: 6 minutes.")

    if st.button(
        "Calculate Flight Plan",
        type="primary",
        use_container_width=True,
    ):
        try:
            if not operation_id.strip():
                raise ValueError("Operation reference cannot be empty.")

            configuration_data = demo_aircraft_configuration().model_dump()
            configuration_data["fuel_type"] = fuel_grade.value
            configuration_data["default_density_kg_per_litre"] = density

            for rate in configuration_data["consumption_rates"]:
                if rate["phase"] == FuelPhase.FLIGHT:
                    rate["consumption_kg_per_hour"] = flight_rate

                if rate["phase"] == FuelPhase.IDLE:
                    rate["consumption_kg_per_hour"] = idle_rate

            configuration = FuelPlanningConfiguration.model_validate(configuration_data)

            planning_legs = []

            for index, (_, row) in enumerate(edited.iterrows(), start=1):
                leg_id = str(row["Leg"]).strip()

                flight_type = FlightType(str(row["Flight Type"]).lower())
                departure_id = str(row["Departure"]).strip().upper()
                destination_id = str(row["Destination"]).strip().upper()

                if not departure_id or not destination_id:
                    raise ValueError(
                        f"{leg_id}: departure and destination are required."
                    )

                FlightLeg(
                    leg_id=leg_id,
                    sequence_number=index,
                    flight_type=flight_type,
                    departure=FlightLocation(
                        location_id=departure_id,
                        name=departure_id,
                    ),
                    destination=FlightLocation(
                        location_id=destination_id,
                        name=destination_id,
                    ),
                    fuel=LegFuelState(tanks=[]),
                )
                minutes = float(row["Flight Minutes"])

                scenic_block = (
                    int(minutes) if flight_type == FlightType.SCENIC else None
                )

                planning_legs.append(
                    FlightPlanningLeg(
                        leg_id=leg_id,
                        flight_type=flight_type,
                        planned_flight_minutes=minutes,
                        additional_idle_minutes=float(row["Additional Idle"]),
                        shutdown_after_leg=bool(row["Shutdown"]),
                        scenic_block_minutes=scenic_block,
                    )
                )
            if len({leg.leg_id for leg in planning_legs}) != len(planning_legs):
                raise ValueError("Flight-leg identifiers must be unique.")

            for previous, current in zip(
                edited.to_dict("records"),
                edited.to_dict("records")[1:],
            ):
                previous_destination = str(previous["Destination"]).strip().upper()

                current_departure = str(current["Departure"]).strip().upper()

                if previous_destination != current_departure:
                    raise ValueError(
                        "Consecutive flight legs must have matching "
                        "destination and departure locations."
                    )
            result = calculate_flight_day_fuel(
                tuple(planning_legs),
                configuration,
                engine_running_at_start=engine_running_at_start,
            )

            st.session_state.last_fuel_result = result
            st.session_state.last_fuel_density = density
            st.session_state.last_operation_id = operation_id

        except (ValueError, TypeError, ValidationError) as error:
            st.session_state.pop("last_fuel_result", None)
            st.error(f"Flight planning validation failed: {error}")

    if "last_fuel_result" in st.session_state:
        result = st.session_state.last_fuel_result
        result_density = st.session_state.last_fuel_density

        st.divider()

        st.subheader("Flight Plan Results")

        a, b, c, d = st.columns(4)

        a.metric(
            "Flight Time",
            f"{result.total_flight_minutes:.0f} min",
        )

        b.metric(
            "Idle Time",
            f"{result.total_idle_minutes:.0f} min",
        )

        c.metric(
            "Total Fuel Consumption",
            format_fuel_quantity(
                result.total_fuel_kg,
                result_density,
                flight_rate,
            ),
        )

        results_table = []

        for leg in result.legs:
            results_table.append(
                {
                    "Leg": leg.leg_id,
                    "Flight (min)": leg.fuel.flight_minutes,
                    "Startup (min)": leg.startup_minutes,
                    "Shutdown (min)": leg.shutdown_minutes,
                    "Additional Idle (min)": leg.additional_idle_minutes,
                    "Total Fuel (kg)": round(
                        leg.fuel.total_fuel.kilograms,
                        2,
                    ),
                    "Total Fuel (L)": round(
                        leg.fuel.total_fuel.litres,
                        2,
                    ),
                    "Flight-Equivalent (min)": round(
                        leg.fuel.total_fuel.minutes,
                        1,
                    ),
                    "Planned Fuel": format_fuel_quantity(
                        leg.fuel.total_fuel.kilograms,
                        result_density,
                        flight_rate,
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(results_table),
            hide_index=True,
            width="stretch",
        )

        st.success(
            "Fuel planning calculation completed. "
            "Tank quantities, reserves and W&B are not yet "
            "included in this screen."
        )


# ---------------------------------------------------------------------
# Future application sections
# ---------------------------------------------------------------------

elif page == "Locations & Map":
    render_location_manager()
    render_route_estimator()

elif page == "Aircraft":
    st.title("Aircraft Profiles")

    st.caption(
        "View aircraft profiles and configuration revisions "
        "stored in the local FlyOps database."
    )

    if not aircraft_profiles:
        st.info("No aircraft profiles are currently available.")

    else:
        st.subheader("Available Aircraft")

        st.dataframe(
            [
                {
                    "Registration": aircraft.registration,
                    "Serial Number": aircraft.serial_number,
                    "Variant ID": aircraft.variant_id,
                    "Aircraft ID": aircraft.aircraft_id,
                }
                for aircraft in aircraft_profiles
            ],
            hide_index=True,
            use_container_width=True,
        )

        if selected_aircraft is not None:
            st.divider()

            st.subheader(f"Selected Aircraft: {selected_aircraft.registration}")

            st.write(
                "**Registration:**",
                selected_aircraft.registration,
            )

            st.write(
                "**Serial number:**",
                selected_aircraft.serial_number,
            )

            st.write(
                "**Variant ID:**",
                selected_aircraft.variant_id,
            )

            if selected_revision is not None:
                st.write(
                    "**Configuration revision:**",
                    selected_revision.revision_number,
                )

                st.write(
                    "**Configuration status:**",
                    selected_revision.configuration_status,
                )

elif page == "Weight & Balance":
    st.title("Weight & Balance")

    st.info(
        "The existing W&B engine and CG envelope graphs "
        "will be integrated into this section."
    )


elif page == "Reports":
    st.title("Reports")

    st.info(
        "The existing HTML operation report generator "
        "will be connected to this section."
    )
