"""Combined report-page renderer for heterogeneous plot specifications.

Route and time plot specifications sharing a ``fig`` value are rendered onto
the same A4 page, with each distinct ``plot`` number becoming one stacked
panel. A single panel must contain specifications of one type only; adding a
new plot-spec type later only requires registering it in
``PANEL_RENDERERS``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ....scenarios.schema import RoutePlotSpecification, TimePlotSpecification
from ...io.cache import ParquetCache
from ..styles.layout import draw_layout
from .report_page import (
    ReportMeta,
    _create_content_axes,
    _plot_route_series,
    _to_page_metadata,
)
from .theme import PlotTheme
from .time_report_page import _plot_time_series_group

logger = logging.getLogger(__name__)

PlotSpec = RoutePlotSpecification | TimePlotSpecification


@dataclass(frozen=True)
class PanelContext:
    """Shared resources available to panel renderers."""

    cache: ParquetCache
    components: pd.DataFrame
    theme: PlotTheme


def _render_route_panel(
    ax: Axes, specs: list[PlotSpec], ctx: PanelContext
) -> bool:
    spec = specs[0]
    assert isinstance(spec, RoutePlotSpecification)
    title = spec.title or f"{spec.route_id}_{spec.property}"
    route_data = ctx.cache.read_route(title)
    envelope = route_data.get("envelope")
    if envelope is None or envelope.empty:
        logger.warning("No cached envelope for route '%s' - skipping render.", title)
        return False
    _plot_route_series(ax, spec, envelope, route_data, ctx.theme)
    return True


def _render_time_panel(ax: Axes, specs: list[PlotSpec], ctx: PanelContext) -> bool:
    time_specs = [s for s in specs if isinstance(s, TimePlotSpecification)]
    if ctx.components.empty:
        logger.warning(
            "No cached component data - skipping time plot subplot for %s.",
            [(s.component, s.property) for s in time_specs],
        )
        return False
    return _plot_time_series_group(ax, time_specs, ctx.components, ctx.theme)


@dataclass(frozen=True)
class PanelRenderer:
    """Renders one homogeneous group of same-type specs onto an axes."""

    render: Callable[[Axes, list[PlotSpec], PanelContext], bool]
    max_specs_per_panel: int | None = None


PANEL_RENDERERS: dict[type, PanelRenderer] = {
    RoutePlotSpecification: PanelRenderer(
        render=_render_route_panel, max_specs_per_panel=1
    ),
    TimePlotSpecification: PanelRenderer(
        render=_render_time_panel, max_specs_per_panel=None
    ),
}


def render_combined_report_pages(
    specs: list[PlotSpec],
    cache: ParquetCache,
    *,
    report_meta_base: ReportMeta,
    theme: PlotTheme | None = None,
) -> list[Figure]:
    """Render route/time plot specs into shared report-style A4 pages."""
    if not specs:
        return []

    theme = theme or PlotTheme()

    components = pd.DataFrame()
    if any(isinstance(s, TimePlotSpecification) for s in specs):
        components = cache.read_components()
        if components.empty:
            logger.warning("No cached component data - time plots will be skipped.")

    ctx = PanelContext(cache=cache, components=components, theme=theme)

    grouped: dict[str, list[PlotSpec]] = {}
    for i, spec in enumerate(specs, start=1):
        key = (spec.fig or "").strip() or f"{type(spec).__name__}{i:03d}"
        grouped.setdefault(key, []).append(spec)

    figures: list[Figure] = []
    for fig_key in sorted(grouped.keys()):
        fig = _create_combined_page_figure(
            grouped[fig_key], ctx, report_meta_base, fig_key
        )
        if fig is not None:
            figures.append(fig)

    return figures


def _create_combined_page_figure(
    specs: list[PlotSpec],
    ctx: PanelContext,
    base_meta: ReportMeta,
    fig_key: str,
) -> Figure | None:
    subplots: dict[int | tuple[str, int], list[PlotSpec]] = {}
    for i, spec in enumerate(specs):
        key: int | tuple[str, int] = spec.plot if spec.plot is not None else ("_", i)
        subplots.setdefault(key, []).append(spec)

    subplot_groups = [
        subplots[k]
        for k in sorted(subplots.keys(), key=lambda k: (isinstance(k, tuple), k))
    ]

    for group in subplot_groups:
        types = {type(spec) for spec in group}
        if len(types) > 1:
            raise ValueError(
                f"Figure '{fig_key}', plot {group[0].plot!r} mixes plot types "
                f"{sorted(t.__name__ for t in types)} - a single panel must "
                "contain specifications of one type only."
            )
        renderer = PANEL_RENDERERS[next(iter(types))]
        if renderer.max_specs_per_panel is not None and len(
            group
        ) > renderer.max_specs_per_panel:
            raise ValueError(
                f"Figure '{fig_key}', plot {group[0].plot!r} has "
                f"{len(group)} {next(iter(types)).__name__} specs but at most "
                f"{renderer.max_specs_per_panel} are allowed in one panel."
            )

    theme = ctx.theme
    fig = _new_figure(theme)
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
        renderer = PANEL_RENDERERS[type(group[0])]
        plotted_any |= renderer.render(ax, group, ctx)

    if not plotted_any:
        _close_figure(fig)
        return None

    return fig


def _new_figure(theme: PlotTheme) -> Figure:
    import matplotlib.pyplot as plt

    return plt.figure(figsize=theme.figure_size)


def _close_figure(fig: Figure) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)
