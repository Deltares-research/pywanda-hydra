"""Shared report-page figure rendering helpers."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ...scenarios import RoutePlotSpecification, TimeSeriesPlotSpecification
from .axes import apply_axis_spec
from .theme import PlotTheme

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


def create_content_axes(figure: Figure, count: int, theme: PlotTheme) -> list[Axes]:
    """Create vertically stacked content axes within the report frame."""
    if count <= 0:
        return []
    total_height = theme.content_top - theme.content_bottom
    row_height = max((total_height - theme.row_gap * (count - 1)) / count, 0.08)
    width = theme.content_right - theme.content_left
    return [
        figure.add_axes(
            (
                theme.content_left,
                theme.content_top - (index + 1) * row_height - index * theme.row_gap,
                width,
                row_height,
            )
        )
        for index in range(count)
    ]


def plot_route_series(
    axes: Axes,
    spec: RoutePlotSpecification,
    envelope: pd.DataFrame,
    route_data: dict[str, pd.DataFrame],
    theme: PlotTheme,
) -> None:
    """Render one route subplot on existing report axes."""
    locations = np.asarray(envelope.index, dtype=float)
    order = np.argsort(locations)
    locations, envelope = locations[order], envelope.iloc[order]
    if "min" in envelope:
        axes.plot(locations, envelope["min"], label="min", color=theme.min_color,
                  linestyle=theme.min_linestyle, linewidth=1.2)
    if "max" in envelope:
        axes.plot(locations, envelope["max"], label="max", color=theme.max_color,
                  linestyle=theme.max_linestyle, linewidth=1.2)
    if {"min", "max"}.issubset(envelope.columns):
        axes.fill_between(locations, envelope["min"], envelope["max"], alpha=theme.envelope_alpha)
    apply_axis_spec(axes, spec.x_axis, axis="x")
    apply_axis_spec(axes, spec.y_axis, axis="y")
    if not spec.x_axis.label:
        axes.set_xlabel("S-distance (m)")
    axes.set_title(spec.title or f"{spec.route_id}_{spec.property}",
                   fontsize=theme.axis_title_size, fontfamily=theme.title_font)
    axes.grid(True, linestyle=theme.grid_linestyle, alpha=theme.grid_alpha)
    _position_legend(axes, theme)


def plot_time_series_group(
    axes: Axes,
    specs: list[TimeSeriesPlotSpecification],
    components: pd.DataFrame,
    theme: PlotTheme,
) -> bool:
    """Draw all configured series in one time-series report panel."""
    if not isinstance(components.columns, pd.MultiIndex):
        return False
    plotted = False
    for spec in specs:
        matching = [
            column for column in components.columns
            if column[0] == spec.component and column[1] == spec.property
        ]
        location = spec.location
        if location is not None:
            located = [column for column in matching if not math.isnan(float(column[2]))]
            if located:
                matching = [min(located, key=lambda column: abs(float(column[2]) - location))]
        for column in matching:
            axes.plot(
                components.index.to_numpy(dtype=float), components[column].to_numpy(dtype=float),
                label=spec.legend or spec.component, color=spec.color, linestyle=spec.style,
                marker=spec.marker, linewidth=1.2,
            )
            plotted = True
    if not plotted:
        logger.warning("No cached data for time plot specs %s.",
                       [(spec.component, spec.property) for spec in specs])
        return False
    lead = specs[0]
    apply_axis_spec(axes, lead.x_axis, axis="x")
    apply_axis_spec(axes, lead.y_axis, axis="y")
    if not lead.x_axis.label:
        axes.set_xlabel("Time (s)")
    axes.set_title(lead.title or f"{lead.component}_{lead.property}",
                   fontsize=theme.axis_title_size, fontfamily=theme.title_font)
    axes.grid(True, linestyle=theme.grid_linestyle, alpha=theme.grid_alpha)
    _position_legend(axes, theme)
    return True


def _position_legend(axes: Axes, theme: PlotTheme) -> None:
    box = axes.get_position()
    shrink = min(0.035, box.height * 0.20)
    axes.set_position((box.x0, box.y0 + shrink, box.width, box.height - shrink))
    axes.legend(
        loc="upper center", bbox_to_anchor=(0.5, -shrink / max(box.height, 1e-9)),
        ncol=5, frameon=True, fontsize=theme.legend_fontsize, prop={"family": theme.legend_font},
    )
