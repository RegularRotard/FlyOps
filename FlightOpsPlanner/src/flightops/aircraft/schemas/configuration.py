"""Validation schemas for aircraft configuration data.

These schemas validate data structure, not operational approval.
All values used for flight planning must be verified against
applicable approved aircraft documentation.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class LoadingStation(BaseModel):
    """An aircraft loading station.

    Arms are measured relative to the aircraft's approved datum.
    Negative arms are permitted where applicable.
    """

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
