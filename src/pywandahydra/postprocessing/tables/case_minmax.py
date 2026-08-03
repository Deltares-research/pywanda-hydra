"""Per-case MIN/MAX table calculation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ...results import ParquetResultStore
from ...scenarios import MinMaxTableSpecification
from .export import save_table

CASE_MINMAX_COLUMNS = ["component", "property", "mode", "value"]


def calculate_case_minmax_table(
    specs: list[MinMaxTableSpecification],
    components: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate requested per-component MIN/MAX values without I/O."""
    if components.empty:
        return pd.DataFrame(columns=CASE_MINMAX_COLUMNS)

    rows: list[dict[str, str | float]] = []
    for spec in specs:
        if isinstance(components.columns, pd.MultiIndex):
            matching = [
                column
                for column in components.columns
                if column[0] == spec.component and column[1] == spec.property
            ]
            if not matching:
                continue
            values = components.loc[:, matching]
            value = values.min().min() if spec.mode == "MIN" else values.max().max()
        else:
            column_name = f"{spec.component}|{spec.property}"
            if column_name not in components.columns:
                continue
            values = components[column_name]
            value = values.min() if spec.mode == "MIN" else values.max()

        rows.append(
            {
                "component": spec.component,
                "property": spec.property,
                "mode": spec.mode,
                "value": float(value),
            }
        )

    return pd.DataFrame(rows, columns=CASE_MINMAX_COLUMNS)


def write_case_minmax_table(
    specs: list[MinMaxTableSpecification],
    store: ParquetResultStore,
    output_dir: Path,
    *,
    export_props: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, ...]:
    """Calculate and persist a per-case MIN/MAX table."""
    data = store.read()
    components = data.components.data if data else pd.DataFrame()
    table = calculate_case_minmax_table(specs, components)
    if table.empty:
        return ()
    return tuple(save_table(table, output_dir, "summary_table", export_props=export_props))
