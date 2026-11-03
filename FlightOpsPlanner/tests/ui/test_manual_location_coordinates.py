"""Tests for manual location coordinate entry."""

import math

import pytest

from app.new_location_dialog import parse_decimal_coordinates


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        ("-6.221944", "39.224444"),
        ("0", "0"),
        ("-90", "180"),
        ("90", "-180"),
        ("  -5.123  ", "  39.456  "),
    ],
)
def test_valid_decimal_coordinates(latitude, longitude):
    result = parse_decimal_coordinates(latitude, longitude)

    assert isinstance(result[0], float)
    assert isinstance(result[1], float)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        ("", "39.22"),
        ("-6.22", ""),
        ("invalid", "39.22"),
        ("-6.22", "invalid"),
        ("91", "39.22"),
        ("-91", "39.22"),
        ("-6.22", "181"),
        ("-6.22", "-181"),
        ("nan", "39.22"),
        ("-6.22", "inf"),
    ],
)
def test_invalid_coordinates_rejected(latitude, longitude):
    with pytest.raises(ValueError):
        parse_decimal_coordinates(latitude, longitude)


def test_southern_hemisphere():
    latitude, longitude = parse_decimal_coordinates(
        "-6.221944",
        "39.224444",
    )

    assert latitude < 0
    assert longitude > 0


def test_nonfinite_coordinates_rejected():
    with pytest.raises(ValueError):
        parse_decimal_coordinates(str(math.inf), "39.22")


def test_coordinate_precision_preserved():
    latitude, longitude = parse_decimal_coordinates(
        "-6.123456789",
        "39.987654321",
    )

    assert latitude == pytest.approx(-6.123456789)
    assert longitude == pytest.approx(39.987654321)
