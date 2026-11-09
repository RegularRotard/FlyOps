"""Tests for revision-bound leg loading assessments."""

from types import SimpleNamespace

import pytest

from flightops.operations.loading import leg_wb_service
from flightops.operations.loading.leg_conditions import (
    CrewLoad,
    FuelStationLoad,
    LegConditionError,
    LegLoadingConditions,
)
from flightops.operations.loading.manifest_adapter import (
    LegStationAssignments,
)
from flightops.operations.manifests.models import LegManifest
from flightops.weight_balance.validation import WBWeightCheck


def test_takeoff_and_landing_use_different_fuel(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        leg_wb_service,
        "get_revision_loading_stations",
        lambda revision: (
            SimpleNamespace(
                station_id="PILOT",
                category="crew",
            ),
            SimpleNamespace(
                station_id="FUEL",
                category="usable_fuel",
            ),
        ),
    )

    def fake_validation(
        revision,
        assignments,
        aircraft,
        *,
        weight_check,
    ):
        calls.append((weight_check, assignments))

        return SimpleNamespace(
            calculation=SimpleNamespace(
                calculation=SimpleNamespace(
                    total_weight_kg=500,
                    cg_mm=1000,
                )
            )
        )

    monkeypatch.setattr(
        leg_wb_service,
        "validate_from_revision",
        fake_validation,
    )

    conditions = LegLoadingConditions(
        leg_uid="LEG001",
        crew=(
            CrewLoad(
                crew_id="C001",
                name="Pilot",
                station_id="PILOT",
                weight_kg=85,
            ),
        ),
        takeoff_fuel=(
            FuelStationLoad(
                station_id="FUEL",
                weight_kg=100,
            ),
        ),
        landing_fuel=(
            FuelStationLoad(
                station_id="FUEL",
                weight_kg=70,
            ),
        ),
    )

    result = leg_wb_service.calculate_leg_wb_conditions(
        manifest=LegManifest(leg_uid="LEG001"),
        station_assignments=LegStationAssignments(
            leg_uid="LEG001",
            passenger_stations={},
            baggage_stations={},
        ),
        passengers={},
        baggage={},
        conditions=conditions,
        revision=SimpleNamespace(),
        aircraft=SimpleNamespace(),
    )

    assert len(calls) == 2

    assert calls[0][0] == WBWeightCheck.TAKEOFF
    assert calls[1][0] == WBWeightCheck.LANDING

    takeoff_fuel = [item.weight for item in calls[0][1] if item.station_id == "FUEL"]

    landing_fuel = [item.weight for item in calls[1][1] if item.station_id == "FUEL"]

    assert takeoff_fuel == [100]
    assert landing_fuel == [70]

    assert result.crew_weight_kg == 85
    assert result.takeoff_fuel_kg == 100
    assert result.landing_fuel_kg == 70

    assert result.complete_for_dispatch is False


def test_rejects_wrong_leg():
    with pytest.raises(
        LegConditionError,
        match="another flight leg",
    ):
        leg_wb_service.calculate_leg_wb_conditions(
            manifest=LegManifest(leg_uid="LEG001"),
            station_assignments=LegStationAssignments(
                leg_uid="LEG001",
                passenger_stations={},
                baggage_stations={},
            ),
            passengers={},
            baggage={},
            conditions=LegLoadingConditions(
                leg_uid="LEG002",
                crew=(),
                takeoff_fuel=(),
                landing_fuel=(),
            ),
            revision=SimpleNamespace(),
            aircraft=SimpleNamespace(),
        )
