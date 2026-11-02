"""Validation schemas for aircraft configuration data.

These schemas validate data structure, not operational approval.
All values used for flight planning must be verified against
applicable approved aircraft documentation.
"""

from enum import StrEnum
from math import isclose

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flightops.weight_balance.units import (
    LengthUnit,
    MassUnit,
    convert_length,
    convert_mass,
)


class ConfigurationStatus(StrEnum):
    DRAFT = "draft"
    STRUCTURALLY_VALID = "structurally_valid"
    OPERATIONALLY_VERIFIED = "operationally_verified"


class TechnicalDocumentReference(BaseModel):
    """Reference to aircraft technical documentation."""

    document_id: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    revision: str | None = None


class MassMeasurement(BaseModel):
    """A mass measurement preserving its original units."""

    model_config = ConfigDict(extra="forbid")

    value: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    unit: MassUnit


class ArmMeasurement(BaseModel):
    """An arm measurement relative to the aircraft datum."""

    model_config = ConfigDict(extra="forbid")

    value: float = Field(
        allow_inf_nan=False,
    )

    unit: LengthUnit


def _measurements_match(
    source_value: float,
    normalized_value: float,
) -> bool:
    """Compare equivalent measurements within conversion tolerance."""

    return isclose(
        source_value,
        normalized_value,
        rel_tol=1e-9,
        abs_tol=1e-6,
    )


class LoadingStationCategory(StrEnum):
    """Classification of aircraft loading stations."""

    CREW = "crew"
    PASSENGER = "passenger"
    BAGGAGE = "baggage"
    CARGO = "cargo"
    USABLE_FUEL = "usable_fuel"
    OTHER = "other"


class LoadingStation(BaseModel):
    """An aircraft loading station.

    Arms are measured relative to the aircraft's approved datum.
    Negative arms are permitted where applicable.
    """

    longitudinal_arm: ArmMeasurement | None = None
    lateral_arm: ArmMeasurement | None = None
    maximum_load: MassMeasurement | None = None
    station_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: LoadingStationCategory = LoadingStationCategory.OTHER
    longitudinal_arm_mm: float = Field(allow_inf_nan=False)
    lateral_arm_mm: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )

    maximum_load_kg: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_source_measurements(self):
        """Verify source-unit measurements match normalized station data."""

        if self.longitudinal_arm is not None:
            converted = convert_length(
                self.longitudinal_arm.value,
                self.longitudinal_arm.unit,
                LengthUnit.MM,
            )

            if not _measurements_match(
                converted,
                self.longitudinal_arm_mm,
            ):
                raise ValueError(
                    "Station longitudinal arm source measurement "
                    "does not match normalized value."
                )

        if self.lateral_arm is not None:
            if self.lateral_arm_mm is None:
                raise ValueError(
                    "A normalized lateral arm is required when "
                    "a source lateral arm is provided."
                )

            converted = convert_length(
                self.lateral_arm.value,
                self.lateral_arm.unit,
                LengthUnit.MM,
            )

            if not _measurements_match(
                converted,
                self.lateral_arm_mm,
            ):
                raise ValueError(
                    "Station lateral arm source measurement "
                    "does not match normalized value."
                )

        if self.maximum_load is not None:
            if self.maximum_load_kg is None:
                raise ValueError(
                    "A normalized maximum load is required when "
                    "a source maximum load is provided."
                )

            converted = convert_mass(
                self.maximum_load.value,
                self.maximum_load.unit,
                MassUnit.KG,
            )

            if not _measurements_match(
                converted,
                self.maximum_load_kg,
            ):
                raise ValueError(
                    "Station maximum load source measurement "
                    "does not match normalized value."
                )

        return self


class AircraftWeightLimits(BaseModel):
    """Aircraft weight limitations in kilograms."""

    model_config = ConfigDict(extra="forbid")

    maximum_takeoff_weight_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    maximum_landing_weight_kg: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    minimum_operating_weight_kg: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_weight_limits(self):
        if (
            self.maximum_landing_weight_kg is not None
            and self.maximum_landing_weight_kg > self.maximum_takeoff_weight_kg
        ):
            raise ValueError(
                "Maximum landing weight cannot exceed maximum takeoff weight."
            )

        if (
            self.minimum_operating_weight_kg is not None
            and self.minimum_operating_weight_kg > self.maximum_takeoff_weight_kg
        ):
            raise ValueError(
                "Minimum operating weight cannot exceed maximum takeoff weight."
            )

        return self


class CGEnvelopePoint(BaseModel):
    """Longitudinal CG limits at a specified aircraft weight."""

    model_config = ConfigDict(extra="forbid")

    weight_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    forward_limit_mm: float = Field(
        allow_inf_nan=False,
    )

    aft_limit_mm: float = Field(
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_cg_limits(self):
        if self.forward_limit_mm >= self.aft_limit_mm:
            raise ValueError("Forward CG limit must be less than aft CG limit.")

        return self


class LongitudinalCGEnvelope(BaseModel):
    """Weight-dependent longitudinal CG limits."""

    model_config = ConfigDict(extra="forbid")

    points: list[CGEnvelopePoint] = Field(
        min_length=2,
    )

    @model_validator(mode="after")
    def validate_points(self):
        weights = [point.weight_kg for point in self.points]

        if weights != sorted(weights):
            raise ValueError("CG envelope points must be ordered by weight.")

        if len(weights) != len(set(weights)):
            raise ValueError("CG envelope weights must be unique.")

        return self


class WeightBalanceConfiguration(BaseModel):
    """Aircraft-specific weight-and-balance configuration."""

    weight_limits: AircraftWeightLimits | None = None
    usable_fuel_classification_reviewed: bool = False
    longitudinal_cg_envelope: LongitudinalCGEnvelope | None = None
    basic_empty_weight: MassMeasurement | None = None

    basic_empty_weight_longitudinal_arm: ArmMeasurement | None = None

    basic_empty_weight_lateral_arm: ArmMeasurement | None = None
    basic_empty_weight_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    basic_empty_weight_longitudinal_arm_mm: float = Field(
        allow_inf_nan=False,
    )

    basic_empty_weight_lateral_arm_mm: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )

    datum_description: str = Field(min_length=1)

    loading_stations: list[LoadingStation] = Field(
        default_factory=list,
    )

    source_document_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_stations(self):
        station_ids = [station.station_id for station in self.loading_stations]

        if len(station_ids) != len(set(station_ids)):
            raise ValueError("Loading station identifiers must be unique.")

        return self

    @model_validator(mode="after")
    def validate_source_measurements(self):
        """Check that source measurements agree with normalized values."""

        if self.basic_empty_weight is not None:
            converted = convert_mass(
                self.basic_empty_weight.value,
                self.basic_empty_weight.unit,
                MassUnit.KG,
            )

            if not isclose(
                converted,
                self.basic_empty_weight_kg,
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                raise ValueError(
                    "Basic empty weight source measurement does not "
                    "match the normalized kilogram value."
                )

        if self.basic_empty_weight_longitudinal_arm is not None:
            converted = convert_length(
                self.basic_empty_weight_longitudinal_arm.value,
                self.basic_empty_weight_longitudinal_arm.unit,
                LengthUnit.MM,
            )

            if not isclose(
                converted,
                self.basic_empty_weight_longitudinal_arm_mm,
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                raise ValueError(
                    "Basic empty weight longitudinal arm source "
                    "measurement does not match the normalized value."
                )
        if self.basic_empty_weight_lateral_arm is not None:
            if self.basic_empty_weight_lateral_arm_mm is None:
                raise ValueError(
                    "A normalized empty-aircraft lateral arm is required "
                    "when a source lateral arm is provided."
                )

            converted = convert_length(
                self.basic_empty_weight_lateral_arm.value,
                self.basic_empty_weight_lateral_arm.unit,
                LengthUnit.MM,
            )

            if not _measurements_match(
                converted,
                self.basic_empty_weight_lateral_arm_mm,
            ):
                raise ValueError(
                    "Empty-aircraft lateral arm source measurement "
                    "does not match normalized value."
                )
        return self


class AircraftConfiguration(BaseModel):
    """Validated structure for an individual aircraft configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)

    registration: str = Field(min_length=1)
    serial_number: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)

    status: ConfigurationStatus = ConfigurationStatus.DRAFT

    weight_balance: WeightBalanceConfiguration | None = None

    technical_documents: list[TechnicalDocumentReference] = Field(
        default_factory=list,
    )

    notes: str | None = None

    @model_validator(mode="after")
    def validate_document_references(self):
        if self.weight_balance is None:
            return self

        document_ids = {document.document_id for document in self.technical_documents}

        source_id = self.weight_balance.source_document_id

        if source_id not in document_ids:
            raise ValueError(
                "Weight-and-balance source document must be "
                "included in technical_documents."
            )

        return self


def validate_aircraft_configuration(
    configuration: dict,
) -> AircraftConfiguration:
    """Validate an aircraft configuration without granting approval."""

    validated = AircraftConfiguration.model_validate(configuration)

    if validated.status == ConfigurationStatus.OPERATIONALLY_VERIFIED:
        raise ValueError(
            "Operational verification cannot be assigned through "
            "the configuration validation service."
        )

    return validated
