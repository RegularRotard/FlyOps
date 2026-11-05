"""Determine keyboard focus targets in the manifest grid."""

import pandas as pd


def find_record_row(
    rows: pd.DataFrame,
    record_id: str | None,
) -> int | None:
    """Find the current displayed row index for a stable record ID."""

    if record_id is None or rows.empty:
        return None

    if "ID" not in rows.columns:
        return None

    matches = rows.index[rows["ID"].astype(str) == str(record_id)]

    if len(matches) != 1:
        return None

    # AG Grid displays rows by position, not DataFrame index.
    return int(rows.index.get_indexer_for(matches)[0])
