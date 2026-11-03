"""Fuel grade to fixed reference-density selection."""

import pytest

from flightops.fuel.standard_density import FuelGrade, fuel_density_kg_per_litre


def test_jet_a1_density():
    assert fuel_density_kg_per_litre(FuelGrade.JET_A1) == pytest.approx(0.800)


def test_avgas_density():
    assert fuel_density_kg_per_litre(FuelGrade.AVGAS) == pytest.approx(0.710)


def test_unknown_fuel_grade_rejected():
    with pytest.raises(ValueError):
        fuel_density_kg_per_litre("Diesel")
