"""Generalized output/export utilities for figures and tables.

Inspired by the multi-format export pattern: PDF figures are written
directly into the output directory, while optional formats use
format-specific subdirectories (e.g. ``png-files/``, ``svg-files/``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

# Default export properties per extension
DEFAULT_FIGURE_EXPORT_PROPS: Dict[str, Dict[str, Any]] = {
    ".pdf": {},
}

OPTIONAL_FIGURE_EXPORT_PROPS: Dict[str, Dict[str, Any]] = {
    ".png": {"transparent": False, "dpi": 300},
    ".svg": {"transparent": True},
}


def build_figure_export_props(
    *,
    include_pdf: bool = True,
    include_png: bool = False,
    include_svg: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Build a figure export map with PDF as the default format.

    Args:
        include_pdf: Include PDF export.
        include_png: Include PNG export.
        include_svg: Include SVG export.

    Returns:
        A mapping of file extension to ``savefig`` keyword arguments.
    """
    export_props: Dict[str, Dict[str, Any]] = {}

    if include_pdf:
        export_props.update(DEFAULT_FIGURE_EXPORT_PROPS)
    if include_png:
        export_props[".png"] = OPTIONAL_FIGURE_EXPORT_PROPS[".png"]
    if include_svg:
        export_props[".svg"] = OPTIONAL_FIGURE_EXPORT_PROPS[".svg"]

    return export_props


DEFAULT_TABLE_EXPORT_PROPS: Dict[str, Dict[str, Any]] = {
    ".csv": {},
}


def savefig(
    fig: Figure,
    output_dir: Path,
    filename: str,
    *,
    export_props: Dict[str, Dict[str, Any]] | None = None,
    close: bool = True,
) -> list[Path]:
    """Save a matplotlib Figure to one or more formats.

    PDF is written directly to ``output_dir`` as ``<filename>.pdf``.
    Optional formats are stored in subdirectories named ``<ext>-files/``
    (e.g. ``png-files/``, ``svg-files/``).

    Args:
        fig: The matplotlib Figure to save.
        output_dir: Base output directory.
        filename: Stem name for the file (without extension).
        export_props: Mapping of extension (e.g. ".pdf") to savefig kwargs.
            Defaults to PDF only.
        close: Whether to close the figure after saving.

    Returns:
        List of paths to saved files.
    """
    if export_props is None:
        export_props = DEFAULT_FIGURE_EXPORT_PROPS

    saved: list[Path] = []

    for ext, kwargs in export_props.items():
        if ext == ".pdf":
            output_dir.mkdir(parents=True, exist_ok=True)
            fig_path = output_dir / f"{filename}{ext}"
        else:
            ext_dir = output_dir / f"{ext.lstrip('.')}-files"
            ext_dir.mkdir(parents=True, exist_ok=True)
            fig_path = ext_dir / f"{filename}{ext}"
        fig.savefig(fig_path, bbox_inches="tight", **kwargs)
        saved.append(fig_path)
        logger.info("Saved figure: %s", fig_path)

    if close:
        import matplotlib.pyplot as plt

        plt.close(fig)

    return saved


def save_table(
    df: pd.DataFrame,
    output_dir: Path,
    filename: str,
    *,
    export_props: Dict[str, Dict[str, Any]] | None = None,
) -> list[Path]:
    """Save a DataFrame to one or more table formats.

    CSV exports are written directly to ``output_dir`` (flat layout).
    Non-CSV formats use extension-specific subdirectories.

    Args:
        df: The DataFrame to export.
        output_dir: Base output directory.
        filename: Stem name for the file (without extension).
        export_props: Mapping of extension (e.g. ".csv") to writer kwargs.
            Defaults to CSV only.

    Returns:
        List of paths to saved files.
    """
    if export_props is None:
        export_props = DEFAULT_TABLE_EXPORT_PROPS

    saved: list[Path] = []

    for ext, kwargs in export_props.items():
        if ext == ".csv":
            output_dir.mkdir(parents=True, exist_ok=True)
            table_path = output_dir / f"{filename}{ext}"
            df.to_csv(table_path, index=False, **kwargs)
        elif ext == ".xlsx":
            ext_dir = output_dir / "xlsx-files"
            ext_dir.mkdir(parents=True, exist_ok=True)
            table_path = ext_dir / f"{filename}{ext}"
            df.to_excel(table_path, index=False, **kwargs)
        elif ext == ".parquet":
            ext_dir = output_dir / "parquet-files"
            ext_dir.mkdir(parents=True, exist_ok=True)
            table_path = ext_dir / f"{filename}{ext}"
            df.to_parquet(table_path, index=False, engine="pyarrow", **kwargs)
        else:
            logger.warning("Unsupported table format: %s — skipping.", ext)
            continue

        saved.append(table_path)
        logger.info("Saved table: %s", table_path)

    return saved
