"""Live manifest record management and cascading deletion."""

from dataclasses import replace

from app.manifest_assignments import reconcile_assignments


def remove_passenger(
    passenger_id,
    passengers,
    baggage,
    assignments,
    loading_assignments,
):
    """Remove a passenger and their owned baggage everywhere."""

    updated_passengers = dict(passengers)
    updated_baggage = dict(baggage)

    updated_passengers.pop(passenger_id, None)

    removed_baggage = {
        baggage_id
        for baggage_id, item in baggage.items()
        if item.owner_passenger_id == passenger_id
    }

    for baggage_id in removed_baggage:
        updated_baggage.pop(baggage_id, None)

    updated_assignments = reconcile_assignments(
        assignments,
        list(assignments),
        updated_passengers,
        updated_baggage,
    )

    updated_loading = {}

    for leg_uid, leg in loading_assignments.items():
        passenger_stations = dict(leg.get("passengers", {}))

        baggage_stations = dict(leg.get("baggage", {}))

        passenger_stations.pop(passenger_id, None)

        for baggage_id in removed_baggage:
            baggage_stations.pop(baggage_id, None)

        updated_loading[leg_uid] = {
            "passengers": passenger_stations,
            "baggage": baggage_stations,
        }

    return (
        updated_passengers,
        updated_baggage,
        updated_assignments,
        updated_loading,
    )


def remove_baggage(
    baggage_id,
    baggage,
    assignments,
    loading_assignments,
    passengers,
):
    """Remove one baggage item from every flight leg."""

    updated_baggage = dict(baggage)
    updated_baggage.pop(baggage_id, None)

    updated_assignments = reconcile_assignments(
        assignments,
        list(assignments),
        passengers,
        updated_baggage,
    )

    updated_loading = {}

    for leg_uid, leg in loading_assignments.items():
        passenger_stations = dict(leg.get("passengers", {}))

        baggage_stations = dict(leg.get("baggage", {}))

        baggage_stations.pop(baggage_id, None)

        updated_loading[leg_uid] = {
            "passengers": passenger_stations,
            "baggage": baggage_stations,
        }

    return (
        updated_baggage,
        updated_assignments,
        updated_loading,
    )


def update_passenger(
    passenger,
    *,
    name,
    weight_kg,
):
    """Update one passenger without changing their ID."""

    return replace(
        passenger,
        name=name,
        declared_weight=None,
        verified_weight=weight_kg,
        weight_unit="kg",
    )


def update_baggage(
    item,
    *,
    description,
    weight_kg,
):
    """Update one baggage item without changing its owner."""

    return replace(
        item,
        description=description,
        declared_weight=None,
        verified_weight=weight_kg,
        weight_unit="kg",
    )
