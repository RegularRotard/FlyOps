"""Tests for connecting manifests to aircraft loading stations."""

import pytest

from flightops.operations.loading.manifest_adapter import (
    LegStationAssignments,
    ManifestLoadingError,
    build_manifest_loading,
)
from flightops.operations.manifests.models import (
    BaggageItem,
    LegManifest,
    Passenger,
)

STATIONS = {
    "SEAT_FRONT",
    "SEAT_REAR_LEFT",
    "SEAT_REAR_RIGHT",
    "BAGGAGE",
}


def passengers():
    return {
        "P001": Passenger(
            passenger_id="P001",
            name="John",
            verified_weight=85,
        ),
        "P002": Passenger(
            passenger_id="P002",
            name="Sarah",
            verified_weight=65,
        ),
    }


def baggage():
    return {
        "B001": BaggageItem(
            baggage_id="B001",
            description="Suitcase",
            owner_passenger_id="P001",
            verified_weight=18,
        )
    }


def manifest():
    return LegManifest(
        leg_uid="LEG_A",
        passenger_ids=frozenset({"P001", "P002"}),
        baggage_ids=frozenset({"B001"}),
    )


def station_assignments():
    return LegStationAssignments(
        leg_uid="LEG_A",
        passenger_stations={
            "P001": "SEAT_FRONT",
            "P002": "SEAT_REAR_LEFT",
        },
        baggage_stations={
            "B001": "BAGGAGE",
        },
    )


def calculate(
    *,
    leg_manifest=None,
    loading=None,
    passenger_records=None,
    baggage_records=None,
):
    return build_manifest_loading(
        leg_manifest if leg_manifest is not None else manifest(),
        loading if loading is not None else station_assignments(),
        passenger_records if passenger_records is not None else passengers(),
        baggage_records if baggage_records is not None else baggage(),
        configured_station_ids=STATIONS,
    )


def test_correct_payload_weight():
    result = calculate()

    assert result.passenger_weight_kg == 150
    assert result.baggage_weight_kg == 18
    assert result.total_payload_kg == 168


def test_assignments_use_kilograms():
    result = calculate()

    assert len(result.assignments) == 3

    assert all(
        assignment.weight_unit.value == "kg" for assignment in result.assignments
    )


def test_passenger_station_preserved():
    result = calculate()

    john = next(
        assignment for assignment in result.assignments if assignment.name == "John"
    )

    assert john.station_id == "SEAT_FRONT"


def test_missing_passenger_station_rejected():
    loading = LegStationAssignments(
        leg_uid="LEG_A",
        passenger_stations={
            "P001": "SEAT_FRONT",
        },
        baggage_stations={
            "B001": "BAGGAGE",
        },
    )

    with pytest.raises(
        ManifestLoadingError,
        match="No loading station",
    ):
        calculate(loading=loading)


def test_duplicate_passenger_station_rejected():
    loading = LegStationAssignments(
        leg_uid="LEG_A",
        passenger_stations={
            "P001": "SEAT_FRONT",
            "P002": "SEAT_FRONT",
        },
        baggage_stations={
            "B001": "BAGGAGE",
        },
    )

    with pytest.raises(
        ManifestLoadingError,
        match="Multiple passengers",
    ):
        calculate(loading=loading)


def test_unknown_station_rejected():
    loading = LegStationAssignments(
        leg_uid="LEG_A",
        passenger_stations={
            "P001": "UNKNOWN",
            "P002": "SEAT_REAR_LEFT",
        },
        baggage_stations={
            "B001": "BAGGAGE",
        },
    )

    with pytest.raises(
        ManifestLoadingError,
        match="Unknown aircraft loading station",
    ):
        calculate(loading=loading)


def test_missing_weight_rejected():
    records = passengers()

    records["P001"] = Passenger(
        passenger_id="P001",
        name="John",
    )

    with pytest.raises(
        ManifestLoadingError,
        match="Missing weight",
    ):
        calculate(passenger_records=records)


def test_wrong_leg_uid_rejected():
    loading = LegStationAssignments(
        leg_uid="OTHER_LEG",
        passenger_stations={},
        baggage_stations={},
    )

    with pytest.raises(
        ManifestLoadingError,
        match="different legs",
    ):
        calculate(loading=loading)


def test_empty_leg_has_no_payload():
    result = calculate(
        leg_manifest=LegManifest(leg_uid="LEG_A"),
        loading=LegStationAssignments(
            leg_uid="LEG_A",
            passenger_stations={},
            baggage_stations={},
        ),
    )

    assert result.total_payload_kg == 0
    assert result.assignments == ()


def test_baggage_can_share_compartment():
    items = baggage()

    items["B002"] = BaggageItem(
        baggage_id="B002",
        description="Backpack",
        verified_weight=7,
    )

    leg = LegManifest(
        leg_uid="LEG_A",
        passenger_ids=frozenset({"P001", "P002"}),
        baggage_ids=frozenset({"B001", "B002"}),
    )

    loading = LegStationAssignments(
        leg_uid="LEG_A",
        passenger_stations={
            "P001": "SEAT_FRONT",
            "P002": "SEAT_REAR_LEFT",
        },
        baggage_stations={
            "B001": "BAGGAGE",
            "B002": "BAGGAGE",
        },
    )

    result = calculate(
        leg_manifest=leg,
        loading=loading,
        baggage_records=items,
    )

    assert result.baggage_weight_kg == 25
