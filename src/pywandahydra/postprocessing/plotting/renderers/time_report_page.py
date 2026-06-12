"""Report-style time-plot page renderer.

Renders TPlots-sheet specifications into the same A4 report layout used
for route plots: specifications sharing a ``fig`` value land on one page,
and within a page each distinct ``plot`` number becomes one stacked
subplot whose series are drawn together.
"""

from __future__ import annotations

import logging
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ....scenarios.schema import TimePlotSpecification
from ...io.cache import ParquetCache
from ..styles.layout import draw_layout
from .common import apply_axis_spec
from .report_page import ReportMeta, _create_content_axes, _to_page_metadata
from .theme import PlotTheme

logger = logging.getLogger(__name__)


def render_time_report_pages(
    specs: list[TimePlotSpecification],
    cache: ParquetCache,
    *,
    report_meta_base: ReportMeta,
    theme: PlotTheme | None = None,
) -> list[Figure]:
    """Render time plots into report-style A4 pages grouped by fig/plot metadata."""
    if not specs:
        return []

    theme = theme or PlotTheme()

    components = cache.read_components()
    if components.empty:
        logger.warning("No cached component data - skipping time plot render.")
        return []

    grouped: dict[str, list[TimePlotSpecification]] = {}
    for i, spec in enumerate(specs, start=1):
        key = (spec.fig or "").strip() or f"{i:03d}"
        grouped.setdefault(key, []).append(spec)

    figures: list[Figure] = []
    for fig_key in sorted(grouped.keys()):
        fig = _create_time_page_figure(
            grouped[fig_key], components, report_meta_base, fig_key, theme
        )
        if fig is not None:
            figures.append(fig)

    return figures


def _create_time_page_figure(
    specs: list[TimePlotSpecification],
    components: pd.DataFrame,
    base_meta: ReportMeta,
    fig_key: str,
    theme: PlotTheme,
) -> Figure | None:
    # One subplot per distinct plot number; specs without a plot number each
    # get their own subplot so they never silently merge.
    subplots: dict[int | tuple[str, int], list[TimePlotSpecification]] = {}
    for i, spec in enumerate(specs):
        key: int | tuple[str, int] = spec.plot if spec.plot is not None else ("_", i)
        subplots.setdefault(key, []).append(spec)

    subplot_groups = [
        subplots[k] for k in sorted(subplots.keys(), key=lambda k: (isinstance(k, tuple), k))
    ]

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
    draw_layout(fig, _to_page_metadata(meta, theme))

    axes = _create_content_axes(fig, len(subplot_groups), theme)
    plotted_any = False
    for ax, group in zip(axes, subplot_groups, strict=False):
        plotted_any |= _plot_time_series_group(ax, group, components, theme)

    if not plotted_any:
        plt.close(fig)
        return None

    return fig


def _plot_time_series_group(
    ax: Axes,
    specs: list[TimePlotSpecification],
    components: pd.DataFrame,
    theme: PlotTheme,
) -> bool:
    """Draw all series of one subplot; returns True when anything was plotted."""
    plotted = False
    for spec in specs:
        for col, label in _select_columns(components, spec):
            ax.plot(
                components.index.to_numpy(dtype=float),
                components[col].to_numpy(dtype=float),
                label=spec.legend or label,
                color=spec.color,
                linestyle=spec.style,
                marker=spec.marker,
                linewidth=1.2,
            )
            plotted = True

    if not plotted:
        logger.warning(
            "No cached data for time plot spec(s) %s - skipping subplot.",
            [(s.component, s.property) for s in specs],
        )
        return False

    lead = specs[0]
    apply_axis_spec(ax, lead.x_axis, axis="x")
    apply_axis_spec(ax, lead.y_axis, axis="y")
    if not lead.x_axis.label:
        ax.set_xlabel("Time (s)")

    title = lead.title or f"{lead.component}_{lead.property}"
    ax.set_title(title, fontsize=theme.axis_title_size, fontfamily=theme.title_font)
    ax.grid(True, linestyle=theme.grid_linestyle, alpha=theme.grid_alpha)

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
        prop={"family": theme.legend_font},
    )
    return True


def _select_columns(
    components: pd.DataFrame,
    spec: TimePlotSpecification,
) -> list[tuple[tuple[str, str, float], str]]:
    """Pick the cached columns matching a spec, honoring its ``location``.

    Returns ``(column, label)`` pairs. For pipes with multiple s-locations and
    no requested location, every location is plotted with an ``@ s=…`` label;
    a requested location selects the single nearest column.
    """
    if not isinstance(components.columns, pd.MultiIndex):
        return []

    matching = [c for c in components.columns if c[0] == spec.component and c[1] == spec.property]
    if not matching:
        return []

    def s_of(col: tuple[str, str, float]) -> float:
        try:
            return float(col[2])
        except (TypeError, ValueError):
            return float("nan")

    if spec.location is not None:
        located = [c for c in matching if not math.isnan(s_of(c))]
        if located:
            target = float(spec.location)
            col = min(located, key=lambda c: abs(s_of(c) - target))
            return [(col, f"{spec.component} @ s={s_of(col):.1f} m")]
        logger.warning(
            "Time plot for '%s' requested location %.1f m but cached data has "
            "no s-locations; using available series.",
            spec.component,
            spec.location,
        )

    out: list[tuple[tuple[str, str, float], str]] = []
    multiple = len(matching) > 1
    for col in matching:
        s = s_of(col)
        if multiple and not np.isnan(s):
            out.append((col, f"{spec.component} @ s={s:.1f} m"))
        else:
            out.append((col, spec.component))
    return out
