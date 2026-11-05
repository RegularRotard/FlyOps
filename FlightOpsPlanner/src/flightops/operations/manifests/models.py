"""Passenger and baggage records for multi-leg flight operations."""

from dataclasses import dataclass, field
from math import isfinite
from uuid import uuid4

SUPPORTED_WEIGHT_UNITS = {"kg", "lb"}

LB_TO_KG = 0.45359237


def new_record_id() -> str:
    """Generate a stable identifier for a manifest record."""
    return uuid4().hex


def validate_weight(
    value: float | None,
    *,
    field_name: str,
) -> None:
    """Reject negative or nonfinite weights."""

    if value is None:
        return

    if not isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be finite and nonnegative.")


def weight_to_kg(
    value: float,
    unit: str,
) -> float:
    """Convert a supported weight to kilograms."""

    if unit == "kg":
        return value

    if unit == "lb":
        return value * LB_TO_KG

    raise ValueError(f"Unsupported weight unit: {unit}")


@dataclass(frozen=True)
class Passenger:
    """A person who may travel on one or more flight legs."""

    passenger_id: str
    name: str
    declared_weight: float | None = None
    verified_weight: float | None = None
    weight_unit: str = "kg"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.passenger_id.strip():
            raise ValueError("Passenger ID is required.")

        if not self.name.strip():
            raise ValueError("Passenger name is required.")

        if self.weight_unit not in SUPPORTED_WEIGHT_UNITS:
            raise ValueError("Unsupported weight unit.")

        validate_weight(
            self.declared_weight,
            field_name="Declared passenger weight",
        )

        validate_weight(
            self.verified_weight,
            field_name="Verified passenger weight",
        )

    @property
    def effective_weight_kg(self) -> float | None:
        """Return verified weight, falling back to declared weight."""

        value = (
            self.verified_weight
            if self.verified_weight is not None
            else self.declared_weight
        )

        if value is None:
            return None

        return weight_to_kg(value, self.weight_unit)

    @property
    def weight_verified(self) -> bool:
        return self.verified_weight is not None


@dataclass(frozen=True)
class BaggageItem:
    """An individual baggage or cargo item."""

    baggage_id: str
    description: str
    owner_passenger_id: str | None = None
    declared_weight: float | None = None
    verified_weight: float | None = None
    weight_unit: str = "kg"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.baggage_id.strip():
            raise ValueError("Baggage ID is required.")

        if not self.description.strip():
            raise ValueError("Baggage description is required.")

        if self.weight_unit not in SUPPORTED_WEIGHT_UNITS:
            raise ValueError("Unsupported weight unit.")

        validate_weight(
            self.declared_weight,
            field_name="Declared baggage weight",
        )

        validate_weight(
            self.verified_weight,
            field_name="Verified baggage weight",
        )

    @property
    def effective_weight_kg(self) -> float | None:
        """Return verified weight, falling back to declared weight."""

        value = (
            self.verified_weight
            if self.verified_weight is not None
            else self.declared_weight
        )

        if value is None:
            return None

        return weight_to_kg(value, self.weight_unit)

    @property
    def weight_verified(self) -> bool:
        return self.verified_weight is not None


@dataclass(frozen=True)
class LegManifest:
    """Passenger and baggage assignments for one specific flight leg."""

    leg_uid: str
    passenger_ids: frozenset[str] = field(default_factory=frozenset)
    baggage_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.leg_uid.strip():
            raise ValueError("Flight-leg UID is required.")

        object.__setattr__(
            self,
            "passenger_ids",
            frozenset(self.passenger_ids),
        )

        object.__setattr__(
            self,
            "baggage_ids",
            frozenset(self.baggage_ids),
        )


@dataclass(frozen=True)
class LegLoad:
    """Calculated passenger and baggage load for one leg."""

    leg_uid: str
    passenger_count: int
    baggage_count: int
    passenger_weight_kg: float
    baggage_weight_kg: float
    total_weight_kg: float
    missing_weight_count: int
    unverified_weight_count: int
    warnings: tuple[str, ...]

    @property
    def ready_for_weight_and_balance(self) -> bool:
        """Whether all assigned load weights are available.

        This does not constitute aircraft or dispatch approval.
        """
        return (
            self.missing_weight_count == 0
            and self.unverified_weight_count == 0
            and not self.warnings
        )
