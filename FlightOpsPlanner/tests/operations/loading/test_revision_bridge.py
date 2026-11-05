"""Tests for revision-bound manifest loading integration."""

from types import SimpleNamespace

import pytest

from flightops.operations.loading import revision_bridge


def test_unpersisted_revision_rejected():
    revision = SimpleNamespace(
        id=None,
        profile_id=None,
        snapshot={},
    )

    with pytest.raises(
        revision_bridge.LoadingIntegrationError,
        match="persisted",
    ):
        revision_bridge.get_revision_loading_stations(revision)


def test_invalid_revision_snapshot_rejected():
    revision = SimpleNamespace(
        id="REV001",
        profile_id="AIRCRAFT001",
        snapshot={},
    )

    with pytest.raises(
        revision_bridge.LoadingIntegrationError,
        match="invalid",
    ):
        revision_bridge.get_revision_loading_stations(revision)


def test_loading_stations_preserve_configured_ids(
    monkeypatch,
):
    """Station IDs must originate from the aircraft configuration."""

    station = SimpleNamespace(
        station_id="CUSTOM_SEAT_001",
        description="Configured passenger seat",
        category=SimpleNamespace(value="passenger"),
    )

    configuration = SimpleNamespace(
        status=revision_bridge.ConfigurationStatus.OPERATIONALLY_VERIFIED,
        weight_balance=SimpleNamespace(
            loading_stations=[station],
        ),
    )

    monkeypatch.setattr(
        revision_bridge.AircraftConfiguration,
        "model_validate",
        lambda snapshot: configuration,
    )

    revision = SimpleNamespace(
        id="REV001",
        profile_id="AIRCRAFT001",
        snapshot={},
    )

    stations = revision_bridge.get_revision_loading_stations(revision)

    assert len(stations) == 1

    assert stations[0].station_id == "CUSTOM_SEAT_001"
    assert stations[0].name == "Configured passenger seat"
    assert stations[0].category == "passenger"


def test_partial_result_cannot_authorize_dispatch():
    """Partial W&B must never be marked dispatch-ready."""

    result = revision_bridge.PartialLegWBResult(
        leg_uid="LEG001",
        aircraft_profile_id="AIRCRAFT001",
        configuration_revision_id="REV001",
        configuration_revision_number=1,
        payload=None,
        calculation=None,
    )

    assert result.complete_for_dispatch is False
