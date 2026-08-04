"""Branded PDF page rendering for route and time-series figures."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ...results import ExtractedSimulationData, ParquetResultStore, RouteIdentity
from ...scenarios import RoutePlotSpecification, TimeSeriesPlotSpecification
from ..plotting.renderers.report_page import ReportMeta, _create_content_axes, _plot_route_series
from ..plotting.renderers.time_report_page import _plot_time_series_group
from .layout import PageMetadata, draw_layout
from .theme import PlotTheme

logger = logging.getLogger(__name__)

PlotSpec = RoutePlotSpecification | TimeSeriesPlotSpecification


def render_combined_report_pages(
    specs: list[PlotSpec],
    store: ParquetResultStore,
    *,
    report_meta_base: ReportMeta,
    theme: PlotTheme | None = None,
) -> list[Figure]:
    """Render route and time-series specifications into A4 report pages."""
    if not specs:
        return []
    data = store.read()
    if data is None:
        logger.warning("No complete result data - report plots will be skipped.")
        return []
    theme = theme or PlotTheme()
    components = data.components.data
    if any(isinstance(spec, TimeSeriesPlotSpecification) for spec in specs) and components.empty:
        logger.warning("No component data - time plots will be skipped.")

    grouped: dict[str, list[PlotSpec]] = {}
    for index, spec in enumerate(specs, start=1):
        key = (spec.fig or "").strip() or f"{type(spec).__name__}{index:03d}"
        grouped.setdefault(key, []).append(spec)

    figures: list[Figure] = []
    for figure_key in sorted(grouped):
        figure = _render_page(
            grouped[figure_key],
            data,
            components,
            report_meta_base,
            figure_key,
            theme,
        )
        if figure is not None:
            figures.append(figure)
    return figures


def _render_page(
    specs: list[PlotSpec],
    data: ExtractedSimulationData,
    components: pd.DataFrame,
    base_meta: ReportMeta,
    figure_key: str,
    theme: PlotTheme,
) -> Figure | None:
    panel_groups = _group_panels(specs, figure_key)
    figure = _new_figure(theme)
    meta = ReportMeta(
        case_name=base_meta.case_name,
        analysis_description=base_meta.analysis_description,
        scenario_description=base_meta.scenario_description,
        chapter=base_meta.chapter,
        project_number=base_meta.project_number,
        figure_id=f"{base_meta.figure_id}{figure_key}",
        wanda_version=base_meta.wanda_version,
        report_date=base_meta.report_date,
    )
    draw_layout(figure, _page_metadata(meta, theme))

    plotted_any = False
    content_axes = _create_content_axes(figure, len(panel_groups), theme)
    for axes, group in zip(content_axes, panel_groups, strict=False):
        plotted_any |= _render_panel(axes, group, data, components, theme)
    if not plotted_any:
        _close_figure(figure)
        return None
    return figure


def _group_panels(specs: list[PlotSpec], figure_key: str) -> list[list[PlotSpec]]:
    panels: dict[int | tuple[str, int], list[PlotSpec]] = {}
    for index, spec in enumerate(specs):
        key: int | tuple[str, int] = spec.plot if spec.plot is not None else ("_", index)
        panels.setdefault(key, []).append(spec)
    sorted_keys = sorted(panels, key=lambda key: (isinstance(key, tuple), key))
    groups = [panels[key] for key in sorted_keys]
    for group in groups:
        types = {type(spec) for spec in group}
        if len(types) > 1:
            raise ValueError(
                f"Figure '{figure_key}', plot {group[0].plot!r} mixes plot types "
                f"{sorted(spec_type.__name__ for spec_type in types)} - a single panel must "
                "contain specifications of one type only."
            )
        if isinstance(group[0], RoutePlotSpecification) and len(group) > 1:
            raise ValueError(
                f"Figure '{figure_key}', plot {group[0].plot!r} has {len(group)} "
                "RoutePlotSpecification specs but at most 1 are allowed in one panel."
            )
    return groups


def _render_panel(
    axes: Axes,
    specs: list[PlotSpec],
    data: ExtractedSimulationData,
    components: pd.DataFrame,
    theme: PlotTheme,
) -> bool:
    first_spec = specs[0]
    if isinstance(first_spec, RoutePlotSpecification):
        route_data = data.routes.get(RouteIdentity(first_spec.route_id, first_spec.property))
        if route_data is None or route_data.envelope is None or route_data.envelope.empty:
            logger.warning(
                "No cached envelope for route '%s' - skipping render.",
                first_spec.title or first_spec.route_id,
            )
            return False
        _plot_route_series(
            axes,
            first_spec,
            route_data.envelope,
            {
                "timeseries": route_data.timeseries,
                "envelope": route_data.envelope,
                "profile": route_data.profile,
            },
            theme,
        )
        return True
    time_specs = [spec for spec in specs if isinstance(spec, TimeSeriesPlotSpecification)]
    if components.empty:
        logger.warning(
            "No cached component data - skipping time plot subplot for %s.",
            [(spec.component, spec.property) for spec in time_specs],
        )
        return False
    return _plot_time_series_group(axes, time_specs, components, theme)


def _new_figure(theme: PlotTheme) -> Figure:
    import matplotlib.pyplot as plt

    return plt.figure(figsize=theme.figure_size)


def _close_figure(figure: Figure) -> None:
    import matplotlib.pyplot as plt

    plt.close(figure)


def _page_metadata(meta: ReportMeta, theme: PlotTheme) -> PageMetadata:
    """Map report metadata to the final page-layout schema."""
    case_description = "\n".join(
        value for value in (meta.scenario_description, meta.case_name) if value and value.strip()
    )
    return PageMetadata(
        title=meta.figure_id or "figure",
        case_title=(meta.analysis_description or meta.case_name or "-").strip(),
        case_description=case_description,
        proj_number=(meta.project_number or "-").strip(),
        section_name=(meta.chapter or "").strip(),
        fig_name=(meta.figure_id or "-").strip(),
        software_version=(meta.wanda_version or "WANDA").strip(),
        date=_parse_report_date(meta.report_date),
        fontsize=theme.footer_fontsize,
        font_family=theme.footer_font,
        watermark_alpha=theme.logo_alpha,
    )


def _parse_report_date(value: str) -> datetime | None:
    """Parse report date values accepted by the scenario document."""
    text = (value or "").strip()
    for format_string in ("%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, format_string)
        except ValueError:
            continue
    return None
