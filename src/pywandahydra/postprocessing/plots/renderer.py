"""Plot renderer — reads cached Parquet data and produces figures.

This module never imports pywanda. All data comes from the ParquetCache.
Figures and tables are exported via the generalized :mod:`..export` utilities
which support multi-format output (png, svg, csv, etc.) in format-specific
subdirectories.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ...scenarios.schema import ExportTableSpecification, RoutePlotSpecification
from ..cache import ParquetCache
from ..export import (
    save_table,
    savefig,
)
from ..plotting.specifications import AxisSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route Plot Renderer
# ---------------------------------------------------------------------------


def render_route_plot(
    spec: RoutePlotSpecification,
    cache: ParquetCache,
    *,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    export_props: Dict[str, Dict[str, Any]] | None = None,
) -> Figure | None:
    """Render a route plot from cached data.

    Args:
        spec: Route plot specification.
        cache: ParquetCache instance for the case.
        output_dir: Base directory for exported figures. Each format is
            PDF is written directly to this directory; optional formats are
            stored in subdirectories (e.g. ``png-files/``, ``svg-files/``).
            If None, figure is returned but not saved.
        filename: Output filename stem. Defaults to a safe title-based stem.
        export_props: Per-format save options. Defaults to PNG + SVG.

    Returns:
        The matplotlib Figure, or None if no data is available.
    """
    title = spec.title or f"{spec.route_id}_{spec.property}"
    df = cache.read_route(title)
    if df.empty:
        logger.warning("No cached route data for '%s' — skipping render.", title)
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each series (component) in the DataFrame
    for col in df.columns:
        label = col[0] if isinstance(col, tuple) else str(col)
        ax.plot(df.index, df[col], label=label)

    # Apply axis specifications
    _apply_axis_spec(ax, spec.x_axis, axis="x")
    _apply_axis_spec(ax, spec.y_axis, axis="y")

    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_dir:
        safe_name = filename or title.replace(" ", "_").replace("/", "_")
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)

    return fig


# ---------------------------------------------------------------------------
# Time-Series Plot Renderer
# ---------------------------------------------------------------------------


def render_time_series_plot(
    components: list[str],
    property_name: str,
    cache: ParquetCache,
    *,
    title: Optional[str] = None,
    x_axis: Optional[AxisSpec] = None,
    y_axis: Optional[AxisSpec] = None,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    export_props: Dict[str, Dict[str, Any]] | None = None,
) -> Figure | None:
    """Render a time-series plot from cached component data.

    Args:
        components: Component identifiers to plot.
        property_name: Property name to plot.
        cache: ParquetCache instance for the case.
        title: Plot title.
        x_axis: X-axis specification.
        y_axis: Y-axis specification.
        output_dir: Base directory for exported figures. Each format is
            PDF is written directly to this directory; optional formats are
            stored in subdirectories (e.g. ``png-files/``, ``svg-files/``).
            If None, figure is returned but not saved.
        filename: Output filename stem. Defaults to a safe title-based stem.
        export_props: Per-format save options. Defaults to PNG + SVG.

    Returns:
        The matplotlib Figure, or None if no data is available.
    """
    df = cache.read_components()
    if df.empty:
        logger.warning("No cached component data — skipping time series render.")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = False

    for comp in components:
        # Look for matching column in MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            matching = [c for c in df.columns if c[0] == comp and c[1] == property_name]
            for col in matching:
                ax.plot(df.index, df[col], label=col[0])
                plotted = True
        else:
            col_name = f"{comp}|{property_name}"
            if col_name in df.columns:
                ax.plot(df.index, df[col_name], label=comp)
                plotted = True

    if not plotted:
        logger.warning("No matching data for components=%s, property=%s", components, property_name)
        plt.close(fig)
        return None

    if x_axis:
        _apply_axis_spec(ax, x_axis, axis="x")
    else:
        ax.set_xlabel("Time [s]")

    if y_axis:
        _apply_axis_spec(ax, y_axis, axis="y")

    ax.set_title(title or f"{property_name}")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_dir:
        safe_name = filename or (title or property_name).replace(" ", "_").replace("/", "_")
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)

    return fig


# ---------------------------------------------------------------------------
# Table Renderer
# ---------------------------------------------------------------------------


def render_table(
    specs: list[ExportTableSpecification],
    cache: ParquetCache,
    *,
    output_dir: Optional[Path] = None,
    export_props: Dict[str, Dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Render a summary table from cached component data.

    Computes min/max aggregates as specified by each ExportTableSpecification.

    Args:
        specs: List of table export specifications.
        cache: ParquetCache instance.
        output_dir: Base directory for exported tables. CSV is written
            directly to this directory.
            If None, only returns DataFrame.
        export_props: Per-format save options. Defaults to CSV only.

    Returns:
        Summary DataFrame with columns: component, property, mode, value.
    """
    df = cache.read_components()
    if df.empty:
        return pd.DataFrame(columns=["component", "property", "mode", "value"])

    rows: list[dict[str, str | float]] = []
    for spec in specs:
        # Find matching columns
        if isinstance(df.columns, pd.MultiIndex):
            matching = [c for c in df.columns if c[0] == spec.component and c[1] == spec.property]
            for col in matching:
                series = df[col]
                value = series.min() if spec.mode == "MIN" else series.max()
                rows.append(
                    {
                        "component": col[0],
                        "property": col[1],
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


# ---------------------------------------------------------------------------
# Aggregated table across all cases
# ---------------------------------------------------------------------------


def aggregate_tables(
    scenarios_dir: Path,
    output_dir: Path,
    run_id: str,
) -> pd.DataFrame:
    """Aggregate per-case summary tables into a single cross-case table.

    Reads each case's ``summary_table.csv`` (in the case directory),
    adds a ``case`` column, and concatenates into one table stored in
    ``output_dir/aggregated_table_{run_id}.csv``.

    Args:
        scenarios_dir: Path to the ``scenarios/`` directory containing case folders.
        output_dir: Directory to write the aggregated CSV.
        run_id: Unique identifier for this run, used in the output filename.

    Returns:
        Combined DataFrame with columns: case, component, property, mode, value.
    """
    frames: list[pd.DataFrame] = []

    for case_dir in sorted(scenarios_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        csv_candidates = [
            case_dir / "summary_table.csv",
            # Legacy paths from older export layouts
            case_dir / "tables" / "summary_table.csv",
            case_dir / "csv-files" / "summary_table.csv",
        ]
        csv_path = next((p for p in csv_candidates if p.exists()), None)
        if csv_path is None:
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_axis_spec(ax: Axes, spec: AxisSpec, *, axis: str) -> None:
    """Apply an AxisSpec to a matplotlib Axes.

    Args:
        ax: The matplotlib Axes.
        spec: The axis specification.
        axis: "x" or "y".
    """
    if axis == "x":
        if spec.label:
            ax.set_xlabel(spec.label)
        if spec.min is not None:
            ax.set_xlim(left=spec.min)
        if spec.max is not None:
            ax.set_xlim(right=spec.max)
    else:
        if spec.label:
            ax.set_ylabel(spec.label)
        if spec.min is not None:
            ax.set_ylim(bottom=spec.min)
        if spec.max is not None:
            ax.set_ylim(top=spec.max)
