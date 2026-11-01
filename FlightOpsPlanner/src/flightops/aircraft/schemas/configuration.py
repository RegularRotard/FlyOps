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


class WeightBalanceConfiguration(BaseModel):
    """Aircraft-specific weight-and-balance configuration."""
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
        station_ids = [
            station.station_id
            for station in self.loading_stations
        ]

        if len(station_ids) != len(set(station_ids)):
            raise ValueError(
                "Loading station identifiers must be unique."
            )

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

        document_ids = {
            document.document_id
            for document in self.technical_documents
        }

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