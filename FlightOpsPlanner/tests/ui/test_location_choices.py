"""Tests for saved-location selection in FlyOps."""

from app.location_choices import (
    LocationChoice,
    format_location_option,
    location_options,
)


def sample_locations():
    return (
        LocationChoice(
            location_id="HTZA",
            name="Zanzibar Airport",
            category="Airport",
            latitude=-6.221944,
            longitude=39.224444,
        ),
        LocationChoice(
            location_id="LOC-001",
            name="North Coast Landing Zone",
            category="Landing Zone",
            latitude=-5.9,
            longitude=39.3,
        ),
    )


def test_location_ids_are_preserved():
    options = location_options(sample_locations())

    assert "HTZA" in options
    assert "LOC-001" in options


def test_airport_display():
    label = format_location_option(
        "HTZA",
        sample_locations(),
    )

    assert "✈️" in label
    assert "HTZA" in label
    assert "Zanzibar Airport" in label


def test_landing_zone_display():
    label = format_location_option(
        "LOC-001",
        sample_locations(),
    )

    assert "🚁" in label
    assert "North Coast Landing Zone" in label


def test_missing_location_is_preserved():
    options = location_options(
        sample_locations(),
        current_id="HTDA",
    )

    assert "HTDA" in options


def test_missing_location_has_warning():
    label = format_location_option(
        "HTDA",
        sample_locations(),
    )

    assert "Not found" in label


def test_empty_location_has_prompt():
    label = format_location_option(
        "",
        sample_locations(),
    )

    assert label == "Select a location..."


def test_location_coordinates_preserved():
    location = sample_locations()[0]

    assert location.latitude == -6.221944
    assert location.longitude == 39.224444


def test_location_name_precedes_identifier():
    locations = sample_locations()

    label = format_location_option("HTZA", locations)

    assert "Zanzibar Airport - HTZA" in label
    assert "HTZA — Zanzibar Airport" not in label


def test_custom_location_name_precedes_identifier():
    location = LocationChoice(
        location_id="LOC000123",
        name="Seacliff",
        category="Landing Zone",
        latitude=-6.22,
        longitude=39.22,
    )

    label = format_location_option(
        "LOC000123",
        (location,),
    )

    assert label == "🚁 Seacliff - LOC000123"
