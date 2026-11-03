"""Tests for W&B fuel timing integration."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightLocation,
    FlightOperation,
    LegFuelState,
    LegFuelTank,
)
from flightops.operations.services.automatic_fuel_reconciliation import (
    TankQuantity,
)
from flightops.operations.services.fuel_timing import TimedLegFuel
from flightops.operations.services.timed_weight_balance import (
    build_timed_wb_leg,
    calculate_timed_operation_weight_balance,
)


def sample_leg():
    """Fictional leg with fuel before startup and after shutdown."""

    return FlightLeg(
        leg_id="LEG-001",
        sequence_number=1,
        departure=FlightLocation(
            location_id="A",
            name="Location A",
        ),
        destination=FlightLocation(
            location_id="B",
            name="Location B",
        ),
        fuel=LegFuelState(
            tanks=[
                LegFuelTank(
                    station_id="MAIN",
                    departure_fuel_kg=120.0,
                    planned_burn_kg=40.8,
                )
            ]
        ),
    )


def sample_timing():
    """Fictional fuel timing with 6-minute startup and shutdown."""

    return TimedLegFuel(
        leg_id="LEG-001",
        before_start_tanks=(TankQuantity("MAIN", 120.0),),
        takeoff_tanks=(TankQuantity("MAIN", 117.6),),
        landing_tanks=(TankQuantity("MAIN", 81.6),),
        after_shutdown_tanks=(TankQuantity("MAIN", 79.2),),
        before_start_fuel_kg=120.0,
        takeoff_fuel_kg=117.6,
        landing_fuel_kg=81.6,
        after_shutdown_fuel_kg=79.2,
    )


def test_takeoff_fuel_used_for_wb():
    wb_leg = build_timed_wb_leg(
        sample_leg(),
        sample_timing(),
    )

    assert wb_leg.fuel.departure_fuel_kg == pytest.approx(117.6)


def test_landing_fuel_used_for_wb():
    wb_leg = build_timed_wb_leg(
        sample_leg(),
        sample_timing(),
    )

    assert wb_leg.fuel.arrival_fuel_kg == pytest.approx(81.6)


def test_only_airborne_burn_is_used_for_wb():
    wb_leg = build_timed_wb_leg(
        sample_leg(),
        sample_timing(),
    )

    assert wb_leg.fuel.planned_burn_kg == pytest.approx(36.0)


def test_original_leg_is_not_modified():
    original = sample_leg()

    build_timed_wb_leg(
        original,
        sample_timing(),
    )

    assert original.fuel.departure_fuel_kg == pytest.approx(120.0)
    assert original.fuel.arrival_fuel_kg == pytest.approx(79.2)


def test_leg_identity_mismatch_rejected():
    timing = replace(
        sample_timing(),
        leg_id="WRONG-LEG",
    )

    with pytest.raises(ValueError, match="different flight leg"):
        build_timed_wb_leg(
            sample_leg(),
            timing,
        )


def test_before_start_mismatch_rejected():
    timing = replace(
        sample_timing(),
        before_start_tanks=(TankQuantity("MAIN", 110.0),),
        before_start_fuel_kg=110.0,
    )

    with pytest.raises(ValueError, match="Before-start fuel mismatch"):
        build_timed_wb_leg(
            sample_leg(),
            timing,
        )


def test_after_shutdown_mismatch_rejected():
    timing = replace(
        sample_timing(),
        after_shutdown_tanks=(TankQuantity("MAIN", 80.0),),
        after_shutdown_fuel_kg=80.0,
    )

    with pytest.raises(ValueError, match="After-shutdown fuel mismatch"):
        build_timed_wb_leg(
            sample_leg(),
            timing,
        )


def test_unknown_tank_rejected():
    timing = replace(
        sample_timing(),
        takeoff_tanks=(TankQuantity("UNKNOWN", 117.6),),
    )

    with pytest.raises(ValueError, match="Fuel station mismatch"):
        build_timed_wb_leg(
            sample_leg(),
            timing,
        )


def test_takeoff_total_mismatch_rejected():
    timing = replace(
        sample_timing(),
        takeoff_fuel_kg=110.0,
    )

    with pytest.raises(ValueError, match="Takeoff fuel total mismatch"):
        build_timed_wb_leg(
            sample_leg(),
            timing,
        )


def test_complete_operation_uses_existing_wb_calculator():
    leg = sample_leg()

    operation = FlightOperation(
        operation_id="OP-001",
        aircraft_profile_id="AIRCRAFT-001",
        configuration_revision_id="REV-001",
        legs=[leg],
    )

    revision = Mock()
    revision.id = "REV-001"

    aircraft = Mock()
    aircraft.id = "AIRCRAFT-001"

    expected_wb = Mock()

    with patch(
        "flightops.operations.services.timed_weight_balance."
        "calculate_leg_weight_balance",
        return_value=expected_wb,
    ) as calculator:
        result = calculate_timed_operation_weight_balance(
            operation,
            (sample_timing(),),
            revision,
            aircraft,
        )

    assert result.operation_id == "OP-001"
    assert result.legs == (expected_wb,)

    calculated_leg = calculator.call_args.args[0]

    assert calculated_leg.fuel.departure_fuel_kg == pytest.approx(117.6)
    assert calculated_leg.fuel.arrival_fuel_kg == pytest.approx(81.6)


def test_operation_revision_mismatch_rejected():
    operation = FlightOperation(
        operation_id="OP-001",
        aircraft_profile_id="AIRCRAFT-001",
        configuration_revision_id="REV-001",
        legs=[sample_leg()],
    )

    revision = Mock()
    revision.id = "WRONG-REVISION"

    aircraft = Mock()
    aircraft.id = "AIRCRAFT-001"

    with pytest.raises(ValueError, match="different configuration revision"):
        calculate_timed_operation_weight_balance(
            operation,
            (sample_timing(),),
            revision,
            aircraft,
        )


def test_timing_leg_order_mismatch_rejected():
    operation = FlightOperation(
        operation_id="OP-001",
        aircraft_profile_id="AIRCRAFT-001",
        configuration_revision_id="REV-001",
        legs=[sample_leg()],
    )

    revision = Mock()
    revision.id = "REV-001"

    aircraft = Mock()
    aircraft.id = "AIRCRAFT-001"

    with pytest.raises(ValueError, match="exactly and in order"):
        calculate_timed_operation_weight_balance(
            operation,
            (replace(sample_timing(), leg_id="WRONG-LEG"),),
            revision,
            aircraft,
        )
