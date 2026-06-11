"""Tabular post-processing helpers for per-case and run-level exports."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from ..scenarios.schema import ExportTableSpecification
from .cache import ParquetCache
from .export import save_table

logger = logging.getLogger(__name__)


def render_summary_table(
    specs: list[ExportTableSpecification],
    cache: ParquetCache,
    *,
    output_dir: Path | None = None,
    export_props: dict[str, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Render a summary table from cached component data."""
    df = cache.read_components()
    if df.empty:
        return pd.DataFrame(columns=["component", "property", "mode", "value"])

    rows: list[dict[str, str | float]] = []
    for spec in specs:
        if isinstance(df.columns, pd.MultiIndex):
            matching = [
                c
                for c in df.columns
                if c[0] == spec.component and c[1] == spec.property
            ]
            if not matching:
                continue
            sub = df.loc[:, matching]
            value = sub.min().min() if spec.mode == "MIN" else sub.max().max()
            rows.append(
                {
                    "component": spec.component,
                    "property": spec.property,
                    "mode": spec.mode,
                    "value": float(value),
                }
            )
        else:
            col_name = f"{spec.component}|{spec.property}"
            if col_name in df.columns:
                series = df[col_name]
                value = series.min() if spec.mode == "MIN" else series.max()
                rows.append(
                    {
                        "component": spec.component,
                        "property": spec.property,
                        "mode": spec.mode,
                        "value": float(value),
                    }
                )

    result = pd.DataFrame(rows)

    if output_dir and not result.empty:
        save_table(result, output_dir, "summary_table", export_props=export_props)

    return result


def aggregate_case_tables(
    scenarios_dir: Path,
    output_dir: Path,
    run_id: str,
) -> pd.DataFrame:
    """Aggregate per-case summary tables into a run-level table."""
    frames: list[pd.DataFrame] = []

    for case_dir in sorted(scenarios_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        csv_path = case_dir / "summary_table.csv"
        if not csv_path.exists():
            continue
        case_df = pd.read_csv(csv_path)
        case_df.insert(0, "case", case_dir.name)
        frames.append(case_df)

    if not frames:
        logger.warning("No per-case tables found to aggregate.")
        return pd.DataFrame(columns=["case", "component", "property", "mode", "value"])

    result = pd.concat(frames, ignore_index=True)
    save_table(result, output_dir, f"aggregated_table_{run_id}")
    return result
