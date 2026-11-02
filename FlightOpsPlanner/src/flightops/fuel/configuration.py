"""Aircraft-specific flight and idle fuel-planning assumptions.

Rates are planning assumptions, not certified performance predictions.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FuelPhase(StrEnum):
    """Supported fuel-consumption categories."""

    FLIGHT = "flight"
    IDLE = "idle"


class FuelConsumptionRate(BaseModel):
    """Documented planning fuel-consumption rate."""

    model_config = ConfigDict(extra="forbid")

    phase: FuelPhase

    consumption_kg_per_hour: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    source_document_id: str = Field(min_length=1)

    notes: str | None = None


class FuelPlanningConfiguration(BaseModel):
    """Fuel assumptions associated with an aircraft configuration."""

    model_config = ConfigDict(extra="forbid")

    fuel_type: str = Field(min_length=1)

    default_density_kg_per_litre: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    density_source_document_id: str = Field(min_length=1)

    consumption_rates: list[FuelConsumptionRate] = Field(
        min_length=2,
        max_length=2,
    )

    @model_validator(mode="after")
    def validate_rates(self):
        phases = {rate.phase for rate in self.consumption_rates}

        if phases != {FuelPhase.FLIGHT, FuelPhase.IDLE}:
            raise ValueError(
                "Fuel planning requires exactly one flight "
                "and one idle consumption rate."
            )

        return self

    def rate_for_phase(
        self,
        phase: FuelPhase,
    ) -> FuelConsumptionRate:
        """Return the requested configured rate."""

        for rate in self.consumption_rates:
            if rate.phase == phase:
                return rate

        raise ValueError(f"Missing fuel rate for phase: {phase}")
