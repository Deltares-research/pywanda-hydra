"""Built-in figure theme definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotTheme:
    """Styling and layout knobs for report pages."""

    figure_size: tuple[float, float] = (8.27, 11.69)
    min_color: str = "#000000"
    min_linestyle: str = "-."
    max_color: str = "#FF960D"
    max_linestyle: str = "--"
    current_color: str = "#0D38E0"
    elevation_color: str = "#00CC96"
    elevation_linewidth: float = 2.0
    elevation_alpha: float = 0.40
    envelope_alpha: float = 0.08
    grid_alpha: float = 0.35
    grid_linestyle: str = "--"
    axis_title_size: int = 18
    legend_fontsize: int = 12
    footer_fontsize: int = 8
    logo_alpha: float = 0.30
    title_font: str = "Arial"
    legend_font: str = "Arial"
    footer_font: str = "Arial"
    frame_x0: float = 0.04
    frame_y0: float = 0.03
    content_left: float = 0.14
    content_right: float = 0.88
    content_bottom: float = 0.20
    content_top: float = 0.92
    row_gap: float = 0.09
