"""Tests for generic aircraft weight and balance calculations."""

import pytest

from flightops.weight_balance.calculator import (
    WeightBalanceError,
    calculate_weight_balance,
)
from flightops.weight_balance.models import LoadItem


def test_single_load():
    result = calculate_weight_balance(
        [
            LoadItem(
                name="Aircraft empty weight",
                weight_kg=680,
                arm_mm=2500,
            )
        ]
    )

    assert result.total_weight_kg == 680
    assert result.cg_mm == 2500


def test_multiple_loads():
    result = calculate_weight_balance(
        [
            LoadItem("Empty aircraft", 680, 2500),
            LoadItem("Pilot", 80, 1800),
            LoadItem("Passenger", 75, 1800),
            LoadItem("Fuel", 100, 2400),
        ]
    )

    expected_weight = 935

    expected_moment = 680 * 2500 + 80 * 1800 + 75 * 1800 + 100 * 2400

    expected_cg = expected_moment / expected_weight

    assert result.total_weight_kg == expected_weight
    assert result.total_moment_kg_mm == expected_moment
    assert result.cg_mm == pytest.approx(expected_cg)


def test_negative_load_rejected():
    with pytest.raises(ValueError):
        LoadItem(
            "Invalid baggage",
            -10,
            2500,
        )


def test_empty_load_list_rejected():
    with pytest.raises(WeightBalanceError):
        calculate_weight_balance([])


def test_zero_total_weight_rejected():
    with pytest.raises(WeightBalanceError):
        calculate_weight_balance(
            [
                LoadItem(
                    "Zero load",
                    0,
                    2500,
                )
            ]
        )


def test_load_moment():
    item = LoadItem(
        "Pilot",
        80,
        1800,
    )

    assert item.moment_kg_mm == 144000
