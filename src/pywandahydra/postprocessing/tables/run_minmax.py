"""Run-level MIN/MAX table aggregation and persistence."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from .case_minmax import CASE_MINMAX_COLUMNS
from .export import save_table

logger = logging.getLogger(__name__)

RUN_MINMAX_COLUMNS = ["case", *CASE_MINMAX_COLUMNS]


def combine_case_minmax_tables(case_tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine per-case tables in deterministic case-name order without I/O."""
    frames: list[pd.DataFrame] = []
    for case_name in sorted(case_tables):
        table = case_tables[case_name]
        if table.empty:
            continue
        frame = table.copy()
        frame.insert(0, "case", case_name)
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=RUN_MINMAX_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def write_run_minmax_table(
    scenarios_dir: Path,
    output_dir: Path,
    run_id: str,
    *,
    export_props: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, ...]:
    """Read available case tables, combine them, and persist the run table."""
    case_tables: dict[str, pd.DataFrame] = {}
    if scenarios_dir.is_dir():
        for case_dir in sorted(scenarios_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            table_path = case_dir / "summary_table.csv"
            if not table_path.exists():
                continue
            try:
                case_tables[case_dir.name] = pd.read_csv(table_path)
            except pd.errors.EmptyDataError:
                logger.warning("Ignoring empty case table: %s", table_path)

    table = combine_case_minmax_tables(case_tables)
    if table.empty:
        logger.warning("No per-case tables found to aggregate.")
        return ()
    return tuple(
        save_table(
            table,
            output_dir,
            f"aggregated_table_{run_id}",
            export_props=export_props,
        )
    )
