"""Crew Management page for the FlyOps prototype."""

from uuid import uuid4

import pandas as pd
import streamlit as st

from app.aircraft_catalog import list_aircraft
from app.crew_management_service import (
    CrewManagementError,
    build_pilot_record,
    pilot_warnings,
)
from flightops.crew.roster import (
    load_pilots,
    save_pilots,
)

NEW_RECORD = "__new_pilot__"


def _available_variants(
    pilots,
) -> tuple[list[str], dict[str, str]]:
    """Build variant options from existing aircraft and crew records."""

    labels = {}

    try:
        aircraft = list_aircraft()

    except (FileNotFoundError, RuntimeError):
        aircraft = ()

    for profile in aircraft:
        variant_id = profile.variant_id

        if variant_id not in labels:
            labels[variant_id] = f"{variant_id} — {profile.registration}"

    # Preserve previously recorded qualifications even if an
    # aircraft profile is subsequently removed or unavailable.
    for pilot in pilots.values():
        for variant_id in pilot.qualified_variant_ids:
            labels.setdefault(variant_id, variant_id)

    return sorted(labels), labels


def render_crew_management() -> None:
    """Render pilot register administration."""

    st.title("Crew Management")

    st.caption(
        "Maintain the pilot roster used by Flight Planning. "
        "Records are stored locally and remain available offline."
    )

    st.warning(
        "Development personnel register. Stored credentials "
        "must be independently verified before operational use."
    )

    try:
        pilots = load_pilots()

    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error(f"Unable to read crew register: {error}")
        return

    # ---------------------------------------------------------
    # Crew overview
    # ---------------------------------------------------------

    st.subheader("Pilot Register")

    rows = []

    for pilot in sorted(
        pilots.values(),
        key=lambda item: item.full_name.casefold(),
    ):
        warnings = pilot_warnings(pilot)

        rows.append(
            {
                "Name": pilot.full_name,
                "Weight (kg)": pilot.weight_kg,
                "Licence": pilot.licence_type or "Not recorded",
                "Medical": pilot.medical_status(),
                "Qualifications": len(pilot.qualified_variant_ids),
                "Active": pilot.active,
                "Warnings": len(warnings),
            }
        )

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
        )

    else:
        st.info("No pilots registered. Add the first pilot below.")

    st.divider()

    # ---------------------------------------------------------
    # Select pilot to edit
    # ---------------------------------------------------------

    st.subheader("Add or Edit Pilot")

    pilot_ids = sorted(
        pilots,
        key=lambda pilot_id: pilots[pilot_id].full_name.casefold(),
    )

    selected_id = st.selectbox(
        "Pilot record",
        options=[NEW_RECORD, *pilot_ids],
        format_func=lambda pilot_id: (
            "＋ Add new pilot" if pilot_id == NEW_RECORD else pilots[pilot_id].full_name
        ),
        key="crew_management_selected_pilot",
    )

    existing = None if selected_id == NEW_RECORD else pilots[selected_id]

    variant_options, variant_labels = _available_variants(pilots)

    # ---------------------------------------------------------
    # Pilot editor
    # ---------------------------------------------------------

    with st.form(key=f"crew_management_form_{selected_id}"):
        left, right = st.columns(2)

        with left:
            name = st.text_input(
                "Full name",
                value=(existing.full_name if existing else ""),
            )

            weight = st.number_input(
                "Pilot weight (kg)",
                min_value=0.0,
                value=(existing.weight_kg if existing else None),
                step=0.5,
                format="%.1f",
                placeholder="Enter weight",
            )

            weight_verified = st.text_input(
                "Weight verified on (YYYY-MM-DD)",
                value=(
                    existing.weight_verified_on.isoformat()
                    if existing and existing.weight_verified_on
                    else ""
                ),
                help=("Leave blank if the weight verification date is unknown."),
            )

            active = st.checkbox(
                "Active pilot",
                value=(existing.active if existing else True),
            )

        with right:
            licence_type = st.text_input(
                "Licence type",
                value=(existing.licence_type if existing else ""),
                placeholder="e.g. CPL(H)",
            )

            licence_number = st.text_input(
                "Licence number",
                value=(existing.licence_number if existing else ""),
            )

            medical_expiry = st.text_input(
                "Medical expiry (YYYY-MM-DD)",
                value=(
                    existing.medical_expiry.isoformat()
                    if existing and existing.medical_expiry
                    else ""
                ),
            )

        qualifications = st.multiselect(
            "Recorded aircraft variant qualifications",
            options=variant_options,
            default=(list(existing.qualified_variant_ids) if existing else []),
            format_func=lambda variant_id: variant_labels.get(
                variant_id,
                variant_id,
            ),
            help=(
                "Select only qualifications supported by "
                "verified personnel records. This list "
                "does not establish flight currency."
            ),
        )

        submitted = st.form_submit_button(
            "Save Pilot",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            pilot_id = existing.pilot_id if existing else uuid4().hex

            record = build_pilot_record(
                pilot_id=pilot_id,
                full_name=name,
                weight_kg=weight,
                licence_type=licence_type,
                licence_number=licence_number,
                medical_expiry=medical_expiry,
                weight_verified_on=weight_verified,
                qualified_variant_ids=qualifications,
                active=active,
            )

            updated = dict(pilots)
            updated[pilot_id] = record

            save_pilots(updated)

        except (
            CrewManagementError,
            OSError,
            ValueError,
        ) as error:
            st.error(f"Unable to save pilot: {error}")

        else:
            st.success(f"Saved pilot: {record.full_name}")
            st.rerun()

    # ---------------------------------------------------------
    # Review selected record
    # ---------------------------------------------------------

    if existing:
        st.divider()

        st.subheader("Recorded Credential Review")

        warnings = pilot_warnings(existing)

        st.write(f"**Pilot:** {existing.full_name}")

        st.write(f"**Pilot ID:** {existing.pilot_id}")

        st.write(f"**Weight:** {existing.weight_kg:.1f} kg")

        st.write(
            "**Recorded medical:**",
            existing.medical_status(),
        )

        if warnings:
            for warning in warnings:
                st.warning(warning)

        else:
            st.info(
                "No basic record warnings detected. "
                "This is not confirmation of operational "
                "eligibility or flight currency."
            )

    st.caption(
        "To remove a pilot from flight-planning selection, "
        "edit the record and untick Active pilot. "
        "Historical pilot records are retained."
    )
