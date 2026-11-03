"""Minimal Streamlit application for testing the FlyOps leg editor."""

import pandas as pd
import streamlit as st

from app.flight_leg_editor import render_flight_leg_editor

st.set_page_config(
    page_title="FlyOps UI Tests",
    layout="wide",
)

sample_legs = pd.DataFrame(
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
            "Flight Type": "Charter",
            "Departure": "HTZA",
            "Destination": "HTDA",
            "Flight Minutes": 30.0,
            "Additional Idle": 0.0,
            "Shutdown": True,
        },
    ]
)

edited = render_flight_leg_editor(sample_legs)

st.session_state["ui_test_result"] = edited.to_dict("records")
