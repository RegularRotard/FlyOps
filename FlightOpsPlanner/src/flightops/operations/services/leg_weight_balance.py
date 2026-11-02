"""Revision-bound weight-and-balance assessment for flight legs.

Each leg has independent zero-fuel, departure, and arrival loading
conditions. Results are planning assessments, not flight approvals.
"""

from dataclasses import dataclass

from pydantic import ValidationError

from flightops.aircraft.schemas.configuration import (
    AircraftConfiguration,
    LoadingStationCategory,
)
from flightops.database.models import AircraftProfile, AircraftProfileRevision
from flightops.operations.schemas.flight import (
    FlightLeg,
    FlightOperation,
    LegLoadCategory,
)
from flightops.operations.services.fuel_continuity import (
    FuelContinuityResult,
    RefuelEvent,
    validate_fuel_continuity,
)
from flightops.weight_balance.configuration_adapter import (
    ConfigurationAdapterError,
    WBLoadAssignment,
)
from flightops.weight_balance.revision_validation import (
    RevisionBoundWBResult,
    validate_from_revision,
)
from flightops.weight_balance.units import MassUnit
from flightops.weight_balance.validation import WBWeightCheck


@dataclass(frozen=True)
class LegWeightBalanceResult:
    """Three loading assessments for one flight leg."""

    leg_id: str
    sequence_number: int
    zero_fuel: RevisionBoundWBResult
    departure: RevisionBoundWBResult
    arrival: RevisionBoundWBResult
    departure_location_id: str = ""
    destination_location_id: str = ""

    @property
    def departure_weight_kg(self) -> float:
        return self.departure.validation.total_weight_kg

    @property
    def arrival_weight_kg(self) -> float:
        return self.arrival.validation.total_weight_kg

    @property
    def zero_fuel_weight_kg(self) -> float:
        return self.zero_fuel.validation.total_weight_kg


@dataclass(frozen=True)
class OperationWeightBalanceResult:
    """Integrated loading and fuel-continuity assessment."""

    operation_id: str
    aircraft_profile_id: str
    configuration_revision_id: str

    legs: tuple[LegWeightBalanceResult, ...]

    fuel_continuity: FuelContinuityResult


def _configuration_from_revision(revision):
    """Validate and return the selected aircraft configuration."""

    try:
        configuration = AircraftConfiguration.model_validate(revision.snapshot)
    except ValidationError as exc:
        raise ConfigurationAdapterError(
            "Aircraft configuration revision is invalid."
        ) from exc

    if configuration.weight_balance is None:
        raise ConfigurationAdapterError(
            "Aircraft configuration has no weight-and-balance data."
        )

    return configuration


def calculate_leg_weight_balance(
    leg: FlightLeg,
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
) -> LegWeightBalanceResult:
    """Calculate zero-fuel, departure, and arrival W&B for one leg."""

    configuration = _configuration_from_revision(revision)
    wb = configuration.weight_balance

    if not wb.usable_fuel_classification_reviewed:
        raise ConfigurationAdapterError(
            "Usable-fuel station classifications have not been reviewed."
        )

    stations = {station.station_id: station for station in wb.loading_stations}

    non_fuel_assignments = []

    category_map = {
        LegLoadCategory.CREW: LoadingStationCategory.CREW,
        LegLoadCategory.PASSENGER: LoadingStationCategory.PASSENGER,
        LegLoadCategory.BAGGAGE: LoadingStationCategory.BAGGAGE,
        LegLoadCategory.CARGO: LoadingStationCategory.CARGO,
    }

    for load in leg.loads:
        station = stations.get(load.station_id)

        if station is None:
            raise ConfigurationAdapterError(
                f"Unknown loading station: {load.station_id}"
            )

        if station.category == LoadingStationCategory.USABLE_FUEL:
            raise ConfigurationAdapterError(
                "Non-fuel load assigned to a usable-fuel station."
            )

        expected_category = category_map.get(load.category)

        if expected_category is not None and station.category not in {
            expected_category,
            LoadingStationCategory.OTHER,
        }:
            raise ConfigurationAdapterError(
                f"Incompatible loading station category: {load.station_id}"
            )

        non_fuel_assignments.append(
            WBLoadAssignment(
                station_id=load.station_id,
                name=load.name,
                weight=load.weight_kg,
                weight_unit=MassUnit.KG,
            )
        )

    departure_assignments = list(non_fuel_assignments)
    arrival_assignments = list(non_fuel_assignments)

    for tank in leg.fuel.tanks:
        station = stations.get(tank.station_id)

        if station is None:
            raise ConfigurationAdapterError(f"Unknown fuel station: {tank.station_id}")

        if station.category != LoadingStationCategory.USABLE_FUEL:
            raise ConfigurationAdapterError(
                f"Station is not classified as usable fuel: {tank.station_id}"
            )

        departure_assignments.append(
            WBLoadAssignment(
                station_id=tank.station_id,
                name=f"Departure fuel: {tank.station_id}",
                weight=tank.departure_fuel_kg,
                weight_unit=MassUnit.KG,
            )
        )

        arrival_assignments.append(
            WBLoadAssignment(
                station_id=tank.station_id,
                name=f"Arrival fuel: {tank.station_id}",
                weight=tank.arrival_fuel_kg,
                weight_unit=MassUnit.KG,
            )
        )

    zero_fuel = validate_from_revision(
        revision,
        tuple(non_fuel_assignments),
        aircraft,
        weight_check=WBWeightCheck.TAKEOFF,
    )

    departure = validate_from_revision(
        revision,
        tuple(departure_assignments),
        aircraft,
        weight_check=WBWeightCheck.TAKEOFF,
    )

    arrival = validate_from_revision(
        revision,
        tuple(arrival_assignments),
        aircraft,
        weight_check=WBWeightCheck.LANDING,
    )

    return LegWeightBalanceResult(
        leg_id=leg.leg_id,
        sequence_number=leg.sequence_number,
        zero_fuel=zero_fuel,
        departure=departure,
        arrival=arrival,
        departure_location_id=leg.departure.location_id,
        destination_location_id=leg.destination.location_id,
    )


def calculate_operation_weight_balance(
    operation: FlightOperation,
    revision: AircraftProfileRevision,
    aircraft: AircraftProfile,
    *,
    refuel_events: tuple[RefuelEvent, ...] = (),
) -> OperationWeightBalanceResult:
    """Assess fuel continuity before calculating per-leg W&B.

    A returned result means the modelled fuel quantities reconcile.
    Individual loading conditions may still fail their W&B checks.

    This is not an operational flight approval.
    """

    if operation.aircraft_profile_id != aircraft.id:
        raise ConfigurationAdapterError(
            "Flight operation references a different aircraft."
        )

    if operation.configuration_revision_id != revision.id:
        raise ConfigurationAdapterError(
            "Flight operation references a different configuration revision."
        )

    # Establish fuel continuity before producing an integrated
    # operation assessment.
    fuel_continuity = validate_fuel_continuity(
        operation,
        refuel_events,
    )

    results = tuple(
        calculate_leg_weight_balance(
            leg,
            revision,
            aircraft,
        )
        for leg in operation.legs
    )

    return OperationWeightBalanceResult(
        operation_id=operation.operation_id,
        aircraft_profile_id=aircraft.id,
        configuration_revision_id=revision.id,
        legs=results,
        fuel_continuity=fuel_continuity,
    )
