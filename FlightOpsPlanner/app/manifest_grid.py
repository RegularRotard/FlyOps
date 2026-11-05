import json

"""Integrated AG Grid passenger and baggage register."""

import pandas as pd
from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    JsCode,
)

from app.manifest_grid_focus import find_record_row
from app.manifest_grid_service import clean_baggage_description

COLUMNS = [
    "ID",
    "Type",
    "Description",
    "Weight (kg)",
    "Owner ID",
]


def build_manifest_rows(
    passengers,
    baggage,
) -> pd.DataFrame:
    """Build passenger-centred rows with associated baggage."""

    rows = []

    for passenger in passengers.values():
        rows.append(
            {
                "ID": passenger.passenger_id,
                "Type": "Passenger",
                "Description": passenger.name,
                "Weight (kg)": passenger.effective_weight_kg,
                "Owner ID": "",
            }
        )

        for item in baggage.values():
            if item.owner_passenger_id == passenger.passenger_id:
                rows.append(
                    {
                        "ID": item.baggage_id,
                        "Type": "Bag",
                        "Description": clean_baggage_description(item.description),
                        "Weight (kg)": item.effective_weight_kg,
                        "Owner ID": passenger.passenger_id,
                    }
                )

    for item in baggage.values():
        if item.owner_passenger_id is None:
            rows.append(
                {
                    "ID": item.baggage_id,
                    "Type": "Cargo",
                    "Description": clean_baggage_description(item.description),
                    "Weight (kg)": item.effective_weight_kg,
                    "Owner ID": "",
                }
            )

    return pd.DataFrame(rows, columns=COLUMNS)


def render_manifest_grid(
    rows: pd.DataFrame,
    *,
    key: str,
    focus_record_id: str | None = None,
):
    """Render an editable, keyboard-friendly manifest."""

    builder = GridOptionsBuilder.from_dataframe(rows)

    builder.configure_default_column(
        editable=False,
        resizable=True,
        sortable=False,
        filter=False,
    )

    builder.configure_column(
        "ID",
        hide=True,
    )

    builder.configure_column(
        "Owner ID",
        hide=True,
    )

    builder.configure_column(
        "Type",
        header_name="TYPE",
        width=125,
        editable=False,
    )

    builder.configure_column(
        "Description",
        header_name="NAME / DESCRIPTION",
        editable=True,
        flex=3,
        minWidth=220,
    )

    builder.configure_column(
        "Weight (kg)",
        header_name="WEIGHT (KG)",
        editable=True,
        width=145,
        type=["numericColumn"],
    )

    builder.configure_selection(
        selection_mode="single",
        use_checkbox=False,
    )

    options = builder.build()

    options["singleClickEdit"] = True
    options["stopEditingWhenCellsLoseFocus"] = True

    options["enterNavigatesVertically"] = True
    options["enterNavigatesVerticallyAfterEdit"] = True

    options["suppressMovableColumns"] = True
    options["rowSelection"] = "single"
    options["suppressRowClickSelection"] = False

    options["getRowId"] = JsCode("function(params) { return params.data.ID; }")

    # Indicate passenger, bag and cargo rows visually.
    options["getRowStyle"] = JsCode(
        """
        function(params) {
            if (params.data.Type === "Passenger") {
                return {fontWeight: "600"};
            }

            if (params.data.Type === "Bag") {
                return {opacity: "0.9"};
            }

            return {};
        }
        """
    )

    focus_row = find_record_row(
        rows,
        focus_record_id,
    )

    if focus_row is not None:
        # The grid is remounted when a new record is added.
        # Focus only once, after its initial data has rendered.
        options["onFirstDataRendered"] = JsCode(
            """
            function(params) {
                const rowIndex = FOCUS_ROW;

                window.setTimeout(function() {
                    params.api.ensureIndexVisible(rowIndex);
                    params.api.setFocusedCell(
                        rowIndex,
                        "Description"
                    );
                    params.api.startEditingCell({
                        rowIndex: rowIndex,
                        colKey: "Description"
                    });
                }, 80);
            }
            """.replace(
                "FOCUS_ROW",
                json.dumps(focus_row),
            )
        )

    # Keyboard shortcuts apply only while AG Grid has focus.
    # New rows are saved by the Python controller when edited.
    options["onCellKeyDown"] = JsCode(
        """
        function(params) {
            const event = params.event;

            if (!event || !event.ctrlKey) {
                return;
            }

            let recordType = null;
            let ownerId = "";

            if (event.key === "Enter" && !event.shiftKey) {
                recordType = "Passenger";
            }

            if (
                event.shiftKey &&
                event.key.toLowerCase() === "b"
            ) {
                recordType = "Bag";

                const focused = params.node
                    ? params.node.data
                    : null;

                if (!focused) {
                    return;
                }

                if (focused.Type === "Passenger") {
                    ownerId = focused.ID;
                } else if (focused.Type === "Bag") {
                    ownerId = focused["Owner ID"];
                }

                if (!ownerId) {
                    return;
                }
            }

            if (
                event.shiftKey &&
                event.key.toLowerCase() === "c"
            ) {
                recordType = "Cargo";
            }

            if (!recordType) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            const recordId = "ui_" + crypto.randomUUID();

            const newRow = {
                "ID": recordId,
                "Type": recordType,
                "Description": "",
                "Weight (kg)": null,
                "Owner ID": ownerId
            };

            let insertAt = params.api.getDisplayedRowCount();

            if (recordType === "Bag") {
                insertAt = 0;
                // Insert after the last existing bag of this owner.
                // The authoritative Python grouping logic will
                // re-establish the same ordering after saving.
                params.api.forEachNode(function(node) {
                    if (!node.data) {
                        return;
                    }

                    if (
                        node.data.ID === ownerId ||
                        (
                            node.data.Type === "Bag" &&
                            node.data["Owner ID"] === ownerId
                        )
                    ) {
                        insertAt = Math.max(
                            insertAt,
                            node.rowIndex + 1
                        );
                    }
                });

            }

            if (recordType === "Passenger") {
                // Insert before independent cargo.
                params.api.forEachNode(function(node) {
                    if (
                        node.data &&
                        node.data.Type === "Cargo"
                    ) {
                        insertAt = Math.min(
                            insertAt,
                            node.rowIndex
                        );
                    }
                });
            }

            params.api.applyTransaction({
                add: [newRow],
                addIndex: insertAt
            });

            window.setTimeout(function() {
                const node = params.api.getRowNode(recordId);

                if (!node) {
                    return;
                }

                const index = node.rowIndex;

                params.api.ensureIndexVisible(index);

                params.api.setFocusedCell(
                    index,
                    "Description"
                );

                params.api.startEditingCell({
                    rowIndex: index,
                    colKey: "Description"
                });
            }, 50);
        }
        """
    )

    return AgGrid(
        rows,
        gridOptions=options,
        key=key,
        height=max(
            220,
            min(650, 80 + len(rows) * 38),
        ),
        theme="streamlit",
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        update_on=[
            "cellValueChanged",
            "selectionChanged",
        ],
        data_return_mode="as_input",
    )
