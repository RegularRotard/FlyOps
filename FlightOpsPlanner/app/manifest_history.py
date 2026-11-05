"""Undo history for draft passenger and baggage manifests.

History snapshots contain the manifest register and its dependent
flight-leg/loading assignments.

This is session-level draft editing history, not an audit log.
"""

from collections import deque
from copy import deepcopy
from dataclasses import dataclass

MAX_HISTORY = 30


@dataclass(frozen=True)
class ManifestSnapshot:
    """A complete restorable draft-manifest state."""

    passengers: dict
    baggage: dict
    assignments: dict
    loading_assignments: dict
    baggage_overrides: dict
    drafts: dict


@dataclass(frozen=True)
class HistoryEntry:
    """One reversible manifest editing action."""

    description: str
    snapshot: ManifestSnapshot


class ManifestHistory:
    """Bounded undo history for draft manifest changes."""

    def __init__(self, max_entries: int = MAX_HISTORY):
        if max_entries < 1:
            raise ValueError("Manifest history must retain at least one entry.")

        self._entries: deque[HistoryEntry] = deque(maxlen=max_entries)

    @property
    def can_undo(self) -> bool:
        return bool(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def next_description(self) -> str | None:
        if not self._entries:
            return None

        return self._entries[-1].description

    def record(
        self,
        description: str,
        snapshot: ManifestSnapshot,
    ) -> None:
        """Record the state before a successful change."""

        if not description.strip():
            raise ValueError("A history description is required.")

        self._entries.append(
            HistoryEntry(
                description=description,
                snapshot=deepcopy(snapshot),
            )
        )

    def undo(self) -> ManifestSnapshot | None:
        """Return and remove the latest stored state."""

        if not self._entries:
            return None

        entry = self._entries.pop()

        return deepcopy(entry.snapshot)

    def clear(self) -> None:
        """Discard draft history."""

        self._entries.clear()


def capture_manifest_snapshot(
    *,
    passengers: dict,
    baggage: dict,
    assignments: dict,
    loading_assignments: dict,
    baggage_overrides: dict,
    drafts: dict,
) -> ManifestSnapshot:
    """Capture manifest state without sharing mutable references."""

    return ManifestSnapshot(
        passengers=deepcopy(passengers),
        baggage=deepcopy(baggage),
        assignments=deepcopy(assignments),
        loading_assignments=deepcopy(loading_assignments),
        baggage_overrides=deepcopy(baggage_overrides),
        drafts=deepcopy(drafts),
    )


def snapshot_matches(
    snapshot: ManifestSnapshot,
    *,
    passengers: dict,
    baggage: dict,
    assignments: dict,
    loading_assignments: dict,
    baggage_overrides: dict,
    drafts: dict,
) -> bool:
    """Detect whether a manifest operation changed tracked state."""

    return (
        snapshot.passengers == passengers
        and snapshot.baggage == baggage
        and snapshot.assignments == assignments
        and snapshot.loading_assignments == loading_assignments
        and snapshot.baggage_overrides == baggage_overrides
        and snapshot.drafts == drafts
    )
