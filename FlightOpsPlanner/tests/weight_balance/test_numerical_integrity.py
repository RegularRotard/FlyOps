"""Numerical integrity tests for aircraft W&B calculations."""

from math import inf, nan

import pytest

from flightops.weight_balance.calculator import (
    WeightBalanceError,
    calculate_weight_balance,
)
from flightops.weight_balance.models import LoadItem


@pytest.mark.parametrize("weight", [nan, inf, -inf])
def test_nonfinite_weight_rejected(weight):
    with pytest.raises(ValueError):
        LoadItem("Pilot", weight, 2000)


@pytest.mark.parametrize("arm", [nan, inf, -inf])
def test_nonfinite_arm_rejected(arm):
    with pytest.raises(ValueError):
        LoadItem("Pilot", 80, arm)


def test_negative_arm_allowed():
    item = LoadItem("Forward equipment", 25, -500)

    assert item.moment_kg_mm == -12500


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        LoadItem("", 80, 2000)


def test_moment_overflow_rejected():
    with pytest.raises(ValueError):
        LoadItem("Extreme load", 1e308, 1e308)


def test_total_moment_overflow_rejected():
    loads = [
        LoadItem("Load A", 1e100, 1e208),
        LoadItem("Load B", 1e100, 1e208),
    ]

    with pytest.raises(WeightBalanceError):
        calculate_weight_balance(loads)



def test_valid_calculation_unchanged():
    loads = [
        LoadItem("Empty aircraft", 680, 2500),
        LoadItem("Pilot", 80, 1800),
        LoadItem("Fuel", 100, 2400),
    ]

    result = calculate_weight_balance(loads)

    assert result.total_weight_kg == 860

    assert result.total_moment_kg_mm == pytest.approx(
        680 * 2500 + 80 * 1800 + 100 * 2400
    )

    assert result.cg_mm == pytest.approx(
        result.total_moment_kg_mm / 860
    )
