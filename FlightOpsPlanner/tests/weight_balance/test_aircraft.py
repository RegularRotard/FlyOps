"""Tests for aircraft-specific loading station definitions."""

import pytest

from flightops.weight_balance.aircraft import (
    AircraftWBSpecification,
    LoadAssignment,
    LoadingStation,
    StationType,
    resolve_loads,
)
from flightops.weight_balance.calculator import calculate_weight_balance
from flightops.weight_balance.units import LengthUnit, MassUnit


@pytest.fixture
def specification():
    return AircraftWBSpecification(
        aircraft_id="TEST-AIRCRAFT",
        datum_description="Manufacturer-defined reference datum",
        stations=(
            LoadingStation(
                station_id="pilot",
                name="Pilot",
                station_type=StationType.CREW,
                arm=80,
                arm_unit=LengthUnit.IN,
            ),
            LoadingStation(
                station_id="passenger",
                name="Passenger",
                station_type=StationType.PASSENGER,
                arm=210,
                arm_unit=LengthUnit.CM,
            ),
            LoadingStation(
                station_id="baggage",
                name="Baggage",
                station_type=StationType.BAGGAGE,
                arm=-500,
                arm_unit=LengthUnit.MM,
            ),
        ),
    )


def test_mixed_station_units(specification):
    assert specification.get_station("pilot").arm_mm == pytest.approx(2032)

    assert specification.get_station("passenger").arm_mm == pytest.approx(2100)


def test_negative_station_arm(specification):
    assert specification.get_station("baggage").arm_mm == -500


def test_duplicate_station_ids_rejected():
    station = LoadingStation(
        "pilot",
        "Pilot",
        StationType.CREW,
        80,
        LengthUnit.IN,
    )

    with pytest.raises(ValueError, match="unique"):
        AircraftWBSpecification(
            aircraft_id="TEST",
            datum_description="Test datum",
            stations=(station, station),
        )


def test_unknown_station_rejected(specification):
    with pytest.raises(ValueError, match="Unknown loading station"):
        specification.get_station("unknown")


def test_negative_assignment_rejected():
    with pytest.raises(ValueError):
        LoadAssignment(
            "pilot",
            "Invalid",
            -5,
            MassUnit.KG,
        )


def test_resolve_mixed_unit_assignments(specification):
    assignments = (
        LoadAssignment(
            station_id="pilot",
            name="Pilot",
            weight=180,
            weight_unit=MassUnit.LB,
        ),
        LoadAssignment(
            station_id="passenger",
            name="Passenger",
            weight=75,
            weight_unit=MassUnit.KG,
        ),
    )

    loads = resolve_loads(specification, assignments)

    assert loads[0].weight_kg == pytest.approx(81.6466266)
    assert loads[0].arm_mm == pytest.approx(2032)

    assert loads[1].weight_kg == 75
    assert loads[1].arm_mm == 2100


def test_station_loads_work_with_calculator(specification):
    assignments = (
        LoadAssignment("pilot", "Pilot", 80, MassUnit.KG),
        LoadAssignment("passenger", "Passenger", 75, MassUnit.KG),
    )

    loads = resolve_loads(specification, assignments)
    result = calculate_weight_balance(loads)

    expected_moment = (80 * 2032) + (75 * 2100)

    assert result.total_weight_kg == 155
    assert result.total_moment_kg_mm == pytest.approx(expected_moment)
    assert result.cg_mm == pytest.approx(expected_moment / 155)
