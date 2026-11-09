"""Tests for flight-leg loading conditions."""

import pytest

from flightops.operations.loading.leg_conditions import (
    CrewLoad,
    FuelStationLoad,
    LegConditionError,
    LegLoadingConditions,
)


def make_conditions(
    takeoff=100,
    landing=70,
):
    return LegLoadingConditions(
        leg_uid="LEG001",
        crew=(
            CrewLoad(
                crew_id="CREW001",
                name="Pilot",
                station_id="PILOT_SEAT",
                weight_kg=85,
            ),
        ),
        takeoff_fuel=(
            FuelStationLoad(
                station_id="FUEL",
                weight_kg=takeoff,
            ),
        ),
        landing_fuel=(
            FuelStationLoad(
                station_id="FUEL",
                weight_kg=landing,
            ),
        ),
    )


def test_fuel_consumption():
    conditions = make_conditions()

    assert conditions.takeoff_fuel_kg == 100
    assert conditions.landing_fuel_kg == 70
    assert conditions.planned_fuel_consumption_kg == 30


def test_negative_crew_weight_rejected():
    with pytest.raises(LegConditionError):
        CrewLoad(
            crew_id="C001",
            name="Pilot",
            station_id="PILOT",
            weight_kg=-1,
        )


def test_negative_fuel_rejected():
    with pytest.raises(LegConditionError):
        FuelStationLoad(
            station_id="FUEL",
            weight_kg=-5,
        )


def test_landing_fuel_increase_rejected():
    with pytest.raises(
        LegConditionError,
        match="Landing fuel cannot exceed",
    ):
        make_conditions(
            takeoff=50,
            landing=60,
        )


def test_duplicate_crew_rejected():
    crew = CrewLoad(
        crew_id="CREW001",
        name="Pilot",
        station_id="PILOT",
        weight_kg=85,
    )

    with pytest.raises(
        LegConditionError,
        match="Duplicate crew",
    ):
        LegLoadingConditions(
            leg_uid="LEG001",
            crew=(crew, crew),
            takeoff_fuel=(),
            landing_fuel=(),
        )


def test_duplicate_fuel_station_rejected():
    fuel = FuelStationLoad(
        station_id="FUEL",
        weight_kg=50,
    )

    with pytest.raises(
        LegConditionError,
        match="Duplicate takeoff",
    ):
        LegLoadingConditions(
            leg_uid="LEG001",
            crew=(),
            takeoff_fuel=(fuel, fuel),
            landing_fuel=(fuel,),
        )


def test_fuel_station_sets_must_match():
    with pytest.raises(
        LegConditionError,
        match="same configured fuel stations",
    ):
        LegLoadingConditions(
            leg_uid="LEG001",
            crew=(),
            takeoff_fuel=(FuelStationLoad("FUEL_A", 50),),
            landing_fuel=(FuelStationLoad("FUEL_B", 40),),
        )


def test_zero_fuel_condition_is_valid():
    conditions = make_conditions(
        takeoff=0,
        landing=0,
    )

    assert conditions.planned_fuel_consumption_kg == 0
