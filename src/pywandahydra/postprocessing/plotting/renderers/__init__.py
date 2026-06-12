"""Composable rendering routines for postprocessing plots.

This subpackage organizes plotting responsibilities by concern so new renderers
can be added without growing a single monolithic module.
"""

from .theme import PlotTheme

__all__ = [
    "PlotTheme",
    "ReportMeta",
    "render_route_plot",
    "render_route_report_pages",
    "render_time_report_pages",
    "render_time_series_plot",
]


def __getattr__(name: str) -> object:
    """Lazily load renderer symbols to avoid import-time cycles."""
    if name == "ReportMeta":
        from .report_page import ReportMeta

        return ReportMeta
    if name == "render_route_plot":
        from .route_plot import render_route_plot

        return render_route_plot
    if name == "render_route_report_pages":
        from .report_page import render_route_report_pages

        return render_route_report_pages
    if name == "render_time_report_pages":
        from .time_report_page import render_time_report_pages

        return render_time_report_pages
    if name == "render_time_series_plot":
        from .time_series import render_time_series_plot

        return render_time_series_plot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
