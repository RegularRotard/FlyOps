"""Regression tests for aircraft W&B configuration revision integrity."""

from types import SimpleNamespace

import pytest

from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    calculate_from_revision,
)
from tests.weight_balance.test_configuration_adapter import revision_snapshot


def aircraft_profile(
    *,
    aircraft_id="aircraft-001",
    registration="5H-TEST",
    serial_number="TEST-001",
    variant_id="variant-001",
):
    """Create an aircraft profile substitute for identity validation."""

    return SimpleNamespace(
        id=aircraft_id,
        registration=registration,
        serial_number=serial_number,
        variant_id=variant_id,
    )


def test_matching_aircraft_identity_accepted():
    result = calculate_from_revision(
        revision_snapshot(),
        assignments=(),
        aircraft=aircraft_profile(),
    )

    assert result.aircraft_profile_id == "aircraft-001"
    assert result.configuration_revision_id == "revision-001"


@pytest.mark.parametrize(
    ("field", "incorrect_value", "message"),
    [
        ("registration", "5H-WRONG", "registration"),
        ("serial_number", "WRONG-001", "serial number"),
        ("variant_id", "wrong-variant", "variant"),
        ("aircraft_id", "different-aircraft", "different aircraft"),
    ],
)
def test_aircraft_identity_mismatch_rejected(
    field,
    incorrect_value,
    message,
):
    kwargs = {field: incorrect_value}

    with pytest.raises(ConfigurationAdapterError, match=message):
        calculate_from_revision(
            revision_snapshot(),
            assignments=(),
            aircraft=aircraft_profile(**kwargs),
        )


def test_unpersisted_aircraft_rejected():
    with pytest.raises(ConfigurationAdapterError, match="persisted"):
        calculate_from_revision(
            revision_snapshot(),
            assignments=(),
            aircraft=aircraft_profile(aircraft_id=None),
        )


@pytest.mark.parametrize(
    "revision_number",
    [0, -1, None, True, 1.5],
)
def test_invalid_revision_number_rejected(revision_number):
    revision = revision_snapshot()
    revision.revision_number = revision_number

    with pytest.raises(ConfigurationAdapterError, match="revision number"):
        calculate_from_revision(
            revision,
            assignments=(),
        )


def test_historical_revision_remains_calculable():
    """Historical calculations must not require the current revision."""

    revision = revision_snapshot()
    revision.id = "historical-revision"
    revision.revision_number = 1

    result = calculate_from_revision(
        revision,
        assignments=(),
    )

    assert result.configuration_revision_id == "historical-revision"
    assert result.configuration_revision_number == 1
    assert result.calculation.total_weight_kg == 680


def test_historical_registration_preserved():
    """Historical registration is retained in its original snapshot."""

    revision = revision_snapshot()
    revision.id = "historical-revision"
    revision.snapshot["registration"] = "5H-OLD"

    result = calculate_from_revision(
        revision,
        assignments=(),
    )

    assert result.configuration_revision_id == "historical-revision"
    assert revision.snapshot["registration"] == "5H-OLD"
