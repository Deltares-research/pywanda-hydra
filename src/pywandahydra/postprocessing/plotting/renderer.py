"""Plot renderer — reads cached Parquet data and produces figures.

This module never imports pywanda. All data comes from the ParquetCache.
Figures and tables are exported via the generalized :mod:`..export` utilities
which support multi-format output (png, svg, csv, etc.) in format-specific
subdirectories.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from ...scenarios.schema import RoutePlotSpecification
from ..cache import ParquetCache
from ..export import savefig
from .specifications import AxisSpec
from .styles.layout import _default_logo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportMeta:
    """Metadata displayed in the report frame/footer."""

    case_name: str
    analysis_description: str
    scenario_description: str
    chapter: str
    project_number: str
    figure_id: str
    wanda_version: str
    report_date: str


@dataclass(frozen=True)
class PlotTheme:
    """Styling and layout knobs for report pages."""

    figure_size: tuple[float, float] = (8.27, 11.69)  # A4 portrait
    min_color: str = "k"
    min_linestyle: str = "-."
    max_color: str = "#c82536"
    max_linestyle: str = "--"
    current_color: str = "#2f7ea8"
    elevation_color: str = "#8fb59a"
    elevation_linewidth: float = 2.0
    elevation_alpha: float = 0.40
    envelope_alpha: float = 0.08
    grid_alpha: float = 0.35
    grid_linestyle: str = "--"
    axis_title_size: int = 18
    legend_fontsize: int = 12
    footer_fontsize: int = 8
    logo_alpha: float = 0.30

    # Normalized page layout coordinates (0..1)
    frame_x0: float = 0.04
    frame_y0: float = 0.03
    content_left: float = 0.14
    content_right: float = 0.88
    content_bottom: float = 0.20
    content_top: float = 0.92
    row_gap: float = 0.09


def _configure_matplotlib_defaults() -> None:
    """Apply module-level matplotlib defaults for post-processing plots.

    These defaults are process-global (matplotlib rcParams) and ensure
    route/time-series plots do not add extra horizontal padding.
    """
    plt.rcParams.update(
        {
            # Keep x-axis tight by default (no automatic side padding).
            "axes.xmargin": 0.0,
        }
    )


_configure_matplotlib_defaults()


def render_route_report_pages(
    specs: list[RoutePlotSpecification],
    cache: ParquetCache,
    *,
    report_meta_base: ReportMeta,
    theme: PlotTheme | None = None,
) -> list[Figure]:
    """Render route plots into report-style A4 pages grouped by fig/plot metadata."""
    if not specs:
        return []

    theme = theme or PlotTheme()

    grouped: dict[str, list[RoutePlotSpecification]] = {}
    for i, spec in enumerate(specs, start=1):
        key = (spec.fig or "").strip() or f"{i:03d}"
        grouped.setdefault(key, []).append(spec)

    figures: list[Figure] = []
    for fig_key in sorted(grouped.keys()):
        group_specs = sorted(
            grouped[fig_key], key=lambda s: (s.plot if s.plot is not None else 10_000)
        )

        fig = _create_report_page_figure(
            group_specs, cache, report_meta_base, fig_key, theme
        )
        if fig is not None:
            figures.append(fig)

    return figures


def _create_report_page_figure(
    specs: list[RoutePlotSpecification],
    cache: ParquetCache,
    base_meta: ReportMeta,
    fig_key: str,
    theme: PlotTheme,
) -> Figure | None:
    valid_specs: list[
        tuple[RoutePlotSpecification, pd.DataFrame, dict[str, pd.DataFrame]]
    ] = []

    for spec in specs:
        title = spec.title or f"{spec.route_id}_{spec.property}"
        route_data = cache.read_route(title)
        envelope = route_data.get("envelope")
        if envelope is None or envelope.empty:
            logger.warning(
                "No cached envelope for route '%s' – skipping render.", title
            )
            continue
        valid_specs.append((spec, envelope, route_data))

    if not valid_specs:
        return None

    fig = plt.figure(figsize=theme.figure_size)
    meta = ReportMeta(
        case_name=base_meta.case_name,
        analysis_description=base_meta.analysis_description,
        scenario_description=base_meta.scenario_description,
        chapter=base_meta.chapter,
        project_number=base_meta.project_number,
        figure_id=f"{base_meta.figure_id}{fig_key}",
        wanda_version=base_meta.wanda_version,
        report_date=base_meta.report_date,
    )
    _draw_report_frame(fig, meta, theme)

    axes = _create_content_axes(fig, len(valid_specs), theme)
    for ax, (spec, envelope, route_data) in zip(axes, valid_specs, strict=False):
        _plot_route_series(ax, spec, envelope, route_data, theme)

    return fig


def _create_content_axes(fig: Figure, count: int, theme: PlotTheme) -> list[Axes]:
    """Create vertically stacked content axes within the report frame."""
    if count <= 0:
        return []

    total_h = theme.content_top - theme.content_bottom
    total_gap = theme.row_gap * (count - 1)
    row_h = max((total_h - total_gap) / count, 0.08)

    axes: list[Axes] = []
    top = theme.content_top
    width = theme.content_right - theme.content_left

    for i in range(count):
        y0 = top - (i + 1) * row_h - i * theme.row_gap
        axes.append(fig.add_axes((theme.content_left, y0, width, row_h)))

    return axes


def _plot_route_series(
    ax: Axes,
    spec: RoutePlotSpecification,
    envelope: pd.DataFrame,
    route_data: dict[str, pd.DataFrame],
    theme: PlotTheme,
) -> None:
    """Render a single route subplot on an existing axes."""
    s_loc = np.asarray(envelope.index, dtype=float)
    sort_idx_s = np.argsort(s_loc)
    s_loc = s_loc[sort_idx_s]
    envelope = envelope.iloc[sort_idx_s]

    zero_s = _extract_time_zero_series(route_data)
    if zero_s is not None:
        ax.plot(
            zero_s.index.to_numpy(dtype=float),
            zero_s.to_numpy(dtype=float),
            label="0 s",
            color=theme.current_color,
            linewidth=1.2,
        )

    if "min" in envelope.columns:
        ax.plot(
            s_loc,
            envelope["min"],
            label="min",
            color=theme.min_color,
            linestyle=theme.min_linestyle,
            linewidth=1.2,
            zorder=-1,
        )
    if "max" in envelope.columns:
        ax.plot(
            s_loc,
            envelope["max"],
            label="max",
            color=theme.max_color,
            linestyle=theme.max_linestyle,
            linewidth=1.2,
            zorder=-1,
        )
    if {"min", "max"}.issubset(envelope.columns):
        ax.fill_between(
            s_loc, envelope["min"], envelope["max"], alpha=theme.envelope_alpha
        )

    # Match reference behavior: only Head plots show the pipeline elevation profile.
    if spec.property.strip().lower() == "head":
        s_prof, elev_prof = _extract_profile_series(route_data)
        if s_prof is not None and elev_prof is not None:
            ax.plot(
                s_prof,
                elev_prof,
                label="Elevation",
                color=theme.elevation_color,
                linewidth=theme.elevation_linewidth,
                alpha=theme.elevation_alpha,
                zorder=-2,
            )

    _apply_axis_spec(ax, spec.x_axis, axis="x")
    _apply_axis_spec(ax, spec.y_axis, axis="y")
    if not spec.x_axis.label:
        ax.set_xlabel("S-distance (m)")

    title = spec.title or f"{spec.route_id}_{spec.property}"
    ax.set_title(title, fontsize=theme.axis_title_size)
    ax.grid(True, linestyle=theme.grid_linestyle, alpha=theme.grid_alpha)

    _annotate_route_endpoints(ax, route_data)

    box = ax.get_position()
    shrink = min(0.035, box.height * 0.20)
    ax.set_position((box.x0, box.y0 + shrink, box.width, box.height - shrink))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -shrink / max(box.height, 1e-9)),
        fancybox=True,
        shadow=True,
        ncol=5,
        frameon=True,
        fontsize=theme.legend_fontsize,
    )


def _extract_time_zero_series(route_data: dict[str, pd.DataFrame]) -> pd.Series | None:
    """Extract a 0 s series from cached route timeseries if available."""
    ts = route_data.get("timeseries")
    if ts is None or ts.empty:
        return None
    if not isinstance(ts.columns, pd.MultiIndex) or ts.columns.nlevels < 3:
        return None
    if len(ts.index) == 0:
        return None

    row0 = ts.iloc[0]
    s_vals: list[float] = []
    y_vals: list[float] = []
    for col, val in row0.items():
        try:
            s = float(col[2])
            y = float(val)
        except Exception:
            continue
        if np.isnan(s) or np.isnan(y):
            continue
        s_vals.append(s)
        y_vals.append(y)

    if not s_vals:
        return None

    ser = pd.Series(y_vals, index=pd.Index(s_vals, name="s_location [m]"))
    return ser.groupby(level=0).mean().sort_index()


def _annotate_route_endpoints(ax: Axes, route_data: dict[str, pd.DataFrame]) -> None:
    """Annotate start/end component labels from cached timeseries columns."""
    ts = route_data.get("timeseries")
    if (
        ts is None
        or ts.empty
        or not isinstance(ts.columns, pd.MultiIndex)
        or ts.columns.nlevels < 3
    ):
        return

    points: list[tuple[float, str]] = []
    for col in ts.columns:
        try:
            s = float(col[2])
        except Exception:
            continue
        if np.isnan(s):
            continue
        points.append((s, str(col[0])))

    if not points:
        return

    points.sort(key=lambda x: x[0])
    start_label = points[0][1]
    end_label = points[-1][1]

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    stepx = (xmax - xmin) * 0.05
    stepy = (ymax - ymin) * 0.05
    ax.text(xmin + stepx, ymin + stepy, start_label)
    ax.text(xmax - 3 * stepx, ymin + stepy, end_label)


def _extract_profile_series(
    route_data: dict[str, pd.DataFrame],
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Extract profile s/elevation arrays from cached route payload."""
    profile = route_data.get("profile")
    if profile is None or profile.empty or "elevation" not in profile.columns:
        return None, None

    s = np.asarray(profile.index, dtype=float)
    elev = np.asarray(profile["elevation"], dtype=float)
    if len(s) == 0 or len(s) != len(elev):
        return None, None

    sort_idx = np.argsort(s)
    return s[sort_idx], elev[sort_idx]


def _draw_report_frame(fig: Figure, meta: ReportMeta, theme: PlotTheme) -> None:
    """Draw the reference-like frame/footer and watermark on a figure."""
    xo = theme.frame_x0
    yo = theme.frame_y0
    textbox_height = 0.75

    v0 = xo
    v1 = 0.62 + xo
    v2 = 0.81
    v3 = 1.0 - xo

    h0 = yo
    h1 = 1.2 * textbox_height / 29.7 + yo
    h2 = 2.4 * textbox_height / 29.7 + yo
    h3 = 3.6 * textbox_height / 29.7 + yo

    ax = fig.add_axes((0, 0, 1, 1), facecolor=(1, 1, 1, 0))
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    ax.axhline(y=h3, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    ax.axvline(x=v1, ymin=h0, ymax=h3, linewidth=1.5, color="k")
    ax.axhline(y=h1, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    ax.axvline(x=v2, ymin=h0, ymax=h1, linewidth=1.5, color="k")
    ax.axvline(x=v2, ymin=h2, ymax=h3, linewidth=1.5, color="k")
    ax.axhline(y=h2, xmin=v1, xmax=v3, linewidth=1.5, color="k")

    rect = Rectangle((xo, yo), 1 - (2 * xo), 1 - (2 * yo), fill=False, linewidth=1.5)
    ax.add_patch(rect)

    left_text = "\n".join(
        [
            x
            for x in (
                meta.analysis_description,
                meta.scenario_description,
                meta.case_name,
            )
            if x
        ]
    )
    fig.text(
        v0 + 0.01,
        h3 - (h3 - h1) / 2.0,
        left_text,
        va="center",
        ha="left",
        color="black",
        fontsize=theme.footer_fontsize,
    )
    fig.text(
        (v1 + (v2 - v1) / 2.0),
        h2 + (h3 - h2) / 2.0,
        meta.chapter,
        va="center",
        ha="center",
        color="black",
        fontsize=theme.footer_fontsize,
    )
    fig.text(
        (v1 + (v2 - v1) / 2.0),
        (h0 + (h1 - h0) / 2.0),
        meta.project_number,
        va="center",
        ha="center",
        color="black",
        fontsize=theme.footer_fontsize,
    )
    fig.text(
        (v2 + (v3 - v2) / 2.0),
        h2 + (h3 - h2) / 2.0,
        meta.report_date,
        va="center",
        ha="center",
        color="black",
        fontsize=theme.footer_fontsize,
    )
    fig.text(
        (v2 + (v3 - v2) / 2.0),
        (h0 + (h1 - h0) / 2.0),
        meta.figure_id,
        va="center",
        ha="center",
        color="black",
        fontsize=theme.footer_fontsize,
    )
    fig.text(
        (v1 + (v3 - v1) / 2.0),
        h1 + (h2 - h1) / 2.0,
        meta.wanda_version,
        va="center",
        ha="center",
        color="black",
        fontsize=theme.footer_fontsize,
    )

    imgax = fig.add_axes((v1, h0, v3 - v1, h3 - h0), zorder=-10)
    imgax.imshow(_default_logo(), alpha=theme.logo_alpha, interpolation="none")
    imgax.axis("off")


# ---------------------------------------------------------------------------
# Route Plot Renderer
# ---------------------------------------------------------------------------


def render_route_plot(
    spec: RoutePlotSpecification,
    cache: ParquetCache,
    *,
    output_dir: Path | None = None,
    filename: str | None = None,
    export_props: dict[str, dict[str, Any]] | None = None,
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
    route_data = cache.read_route(title)
    envelope = route_data.get("envelope")
    if envelope is None or envelope.empty:
        logger.warning("No cached envelope for route '%s' – skipping render.", title)
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    # Sort the envelope by s_location
    s_loc = envelope.index
    sort_idx_s = np.argsort(s_loc)
    s_loc = s_loc[sort_idx_s]
    envelope = envelope.iloc[sort_idx_s]

    if "min" in envelope.columns:
        ax.plot(s_loc, envelope["min"], label="min", linewidth=1.2)
    if "max" in envelope.columns:
        ax.plot(s_loc, envelope["max"], label="max", linewidth=1.2)
    if {"min", "max"}.issubset(envelope.columns):
        ax.fill_between(s_loc, envelope["min"], envelope["max"], alpha=0.15)

    # Apply axis specifications
    _apply_axis_spec(ax, spec.x_axis, axis="x")
    _apply_axis_spec(ax, spec.y_axis, axis="y")
    if not spec.x_axis.label:
        ax.set_xlabel("s_location [m]")

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
    title: str | None = None,
    x_axis: AxisSpec | None = None,
    y_axis: AxisSpec | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
    export_props: dict[str, dict[str, Any]] | None = None,
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
        if isinstance(df.columns, pd.MultiIndex):
            matching = [c for c in df.columns if c[0] == comp and c[1] == property_name]
            for col in matching:
                # 3-level columns carry s_location at col[2]; for non-pipes it is NaN.
                if (
                    len(col) >= 3
                    and isinstance(col[2], float)
                    and not math.isnan(col[2])
                ):
                    label = f"{col[0]} @ s={col[2]:.1f} m"
                else:
                    label = col[0]
                ax.plot(df.index, df[col], label=label)
                plotted = True
        else:
            col_name = f"{comp}|{property_name}"
            if col_name in df.columns:
                ax.plot(df.index, df[col_name], label=comp)
                plotted = True

    if not plotted:
        logger.warning(
            "No matching data for components=%s, property=%s", components, property_name
        )
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
        safe_name = filename or (title or property_name).replace(" ", "_").replace(
            "/", "_"
        )
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)

    return fig


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
