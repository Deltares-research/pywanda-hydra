"""Tabular output utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_TABLE_EXPORT_PROPS: dict[str, dict[str, Any]] = {".csv": {}}


def save_table(
    data: pd.DataFrame,
    output_dir: Path,
    filename: str,
    *,
    export_props: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    """Save a data frame in one or more configured table formats."""
    saved: list[Path] = []
    for extension, options in (export_props or DEFAULT_TABLE_EXPORT_PROPS).items():
        if extension == ".csv":
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"{filename}{extension}"
            data.to_csv(path, index=False, **options)
        elif extension in {".xlsx", ".parquet"}:
            directory = output_dir / f"{extension[1:]}-files"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{filename}{extension}"
            if extension == ".xlsx":
                data.to_excel(path, index=False, **options)
            else:
                data.to_parquet(path, index=False, engine="pyarrow", **options)
        else:
            logger.warning("Unsupported table format: %s", extension)
            continue
        saved.append(path)
    return saved