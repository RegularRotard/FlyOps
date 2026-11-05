"""Tests for integrated AG Grid manifest editing."""

import pytest

from app.manifest_grid_service import (
    ManifestGridError,
    apply_grid_edits,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    Passenger,
)


def sample_registers():
    passengers = {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
            verified_weight=85,
        )
    }

    baggage = {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        )
    }

    return passengers, baggage


def test_edit_passenger_weight():
    import pandas as pd

    passengers, baggage = sample_registers()

    rows = pd.DataFrame(
        [
            {
                "ID": "P001",
                "Description": "John",
                "Weight (kg)": 92,
            }
        ]
    )

    result = apply_grid_edits(
        rows,
        passengers,
        baggage,
    )

    assert result.passengers["P001"].effective_weight_kg == 92


def test_edit_baggage_weight_preserves_owner():
    import pandas as pd

    passengers, baggage = sample_registers()

    rows = pd.DataFrame(
        [
            {
                "ID": "B001",
                "Description": "Large suitcase",
                "Weight (kg)": 20,
            }
        ]
    )

    result = apply_grid_edits(
        rows,
        passengers,
        baggage,
    )

    assert result.baggage["B001"].effective_weight_kg == 20

    assert result.baggage["B001"].owner_passenger_id == "P001"


def test_negative_weight_rejected():
    import pandas as pd

    passengers, baggage = sample_registers()

    rows = pd.DataFrame(
        [
            {
                "ID": "P001",
                "Description": "John",
                "Weight (kg)": -5,
            }
        ]
    )

    with pytest.raises(ManifestGridError):
        apply_grid_edits(
            rows,
            passengers,
            baggage,
        )


def test_missing_description_rejected():
    import pandas as pd

    passengers, baggage = sample_registers()

    rows = pd.DataFrame(
        [
            {
                "ID": "P001",
                "Description": "",
                "Weight (kg)": 85,
            }
        ]
    )

    with pytest.raises(ManifestGridError):
        apply_grid_edits(
            rows,
            passengers,
            baggage,
        )
