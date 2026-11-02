"""Flight classifications and engine-cycle planning inputs."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlightType(StrEnum):
    """Supported FlyOps flight classifications."""

    FERRY = "ferry"
    CHARTER = "charter"
    SCENIC = "scenic"


class FlightPlanningLeg(BaseModel):
    """Fuel-planning information for a single flight leg."""

    model_config = ConfigDict(extra="forbid")

    leg_id: str = Field(min_length=1)

    flight_type: FlightType

    planned_flight_minutes: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    additional_idle_minutes: float = Field(
        default=0,
        ge=0,
        allow_inf_nan=False,
    )

    shutdown_after_leg: bool = True

    scenic_block_minutes: int | None = None

    @model_validator(mode="after")
    def validate_scenic_block(self):
        """Validate fixed-duration scenic flight planning."""

        if self.flight_type == FlightType.SCENIC:
            if self.scenic_block_minutes not in (15, 30):
                raise ValueError("Scenic flights require a 15- or 30-minute block.")

            if self.planned_flight_minutes != self.scenic_block_minutes:
                raise ValueError(
                    "Scenic flight duration must match the selected block."
                )

        elif self.scenic_block_minutes is not None:
            raise ValueError("Scenic blocks are only valid for Scenic flights.")

        return self
