"""Per-leg passenger and baggage manifest calculations."""

from math import fsum, isfinite

from flightops.operations.manifests.models import (
    BaggageItem,
    LegLoad,
    LegManifest,
    Passenger,
)


def calculate_leg_load(
    manifest: LegManifest,
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
) -> LegLoad:
    """Calculate the known passenger and baggage load for a flight leg.

    Missing weights are not treated as zero for operational readiness.
    A numerical subtotal may still be returned for incomplete manifests.
    """

    passenger_weights = []
    baggage_weights = []

    warnings = []
    missing_weight_count = 0
    unverified_weight_count = 0

    for passenger_id in sorted(manifest.passenger_ids):
        passenger = passengers.get(passenger_id)

        if passenger is None:
            warnings.append(f"Unknown passenger: {passenger_id}")
            missing_weight_count += 1
            continue

        weight = passenger.effective_weight_kg

        if weight is None:
            warnings.append(f"Passenger weight missing: {passenger.name}")
            missing_weight_count += 1
        else:
            passenger_weights.append(weight)

            if not passenger.weight_verified:
                warnings.append(f"Passenger weight unverified: {passenger.name}")
                unverified_weight_count += 1

    for baggage_id in sorted(manifest.baggage_ids):
        item = baggage.get(baggage_id)

        if item is None:
            warnings.append(f"Unknown baggage item: {baggage_id}")
            missing_weight_count += 1
            continue

        weight = item.effective_weight_kg

        if weight is None:
            warnings.append(f"Baggage weight missing: {item.description}")
            missing_weight_count += 1
        else:
            baggage_weights.append(weight)

            if not item.weight_verified:
                warnings.append(f"Baggage weight unverified: {item.description}")
                unverified_weight_count += 1

        owner = item.owner_passenger_id

        if owner and owner not in manifest.passenger_ids:
            warnings.append(
                f"Baggage travelling without assigned owner: {item.description}"
            )

        if owner and owner not in passengers:
            warnings.append(f"Baggage references unknown owner: {owner}")

    passenger_total = fsum(passenger_weights)
    baggage_total = fsum(baggage_weights)
    total = fsum((passenger_total, baggage_total))

    if not all(
        isfinite(value)
        for value in (
            passenger_total,
            baggage_total,
            total,
        )
    ):
        raise ValueError("Calculated manifest weight is not finite.")

    return LegLoad(
        leg_uid=manifest.leg_uid,
        passenger_count=len(manifest.passenger_ids),
        baggage_count=len(manifest.baggage_ids),
        passenger_weight_kg=passenger_total,
        baggage_weight_kg=baggage_total,
        total_weight_kg=total,
        missing_weight_count=missing_weight_count,
        unverified_weight_count=unverified_weight_count,
        warnings=tuple(warnings),
    )


def calculate_operation_loads(
    manifests: list[LegManifest],
    passengers: dict[str, Passenger],
    baggage: dict[str, BaggageItem],
) -> dict[str, LegLoad]:
    """Calculate loads for every manifest in an operation."""

    results = {}

    for manifest in manifests:
        if manifest.leg_uid in results:
            raise ValueError(f"Duplicate manifest for leg: {manifest.leg_uid}")

        results[manifest.leg_uid] = calculate_leg_load(
            manifest,
            passengers,
            baggage,
        )

    return results
