"""Time-series plot renderer."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from ...io.cache import ParquetCache
from ...io.export import savefig
from ..models import AxisSpec
from .common import apply_axis_spec, configure_matplotlib_defaults
from .theme import PlotTheme

logger = logging.getLogger(__name__)

configure_matplotlib_defaults()


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
    theme: PlotTheme | None = None,
) -> Figure | None:
    """Render a time-series plot from cached component data."""
    if theme is None:
        theme = PlotTheme()

    df = cache.read_components()
    if df.empty:
        logger.warning("No cached component data - skipping time series render.")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = False

    for comp in components:
        if isinstance(df.columns, pd.MultiIndex):
            matching = [c for c in df.columns if c[0] == comp and c[1] == property_name]
            for col in matching:
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
        apply_axis_spec(ax, x_axis, axis="x")
    else:
        ax.set_xlabel("Time [s]")

    if y_axis:
        apply_axis_spec(ax, y_axis, axis="y")

    ax.set_title(title or f"{property_name}", fontfamily=theme.title_font)
    ax.legend(loc="best", fontsize=8, prop={"family": theme.legend_font})
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_dir:
        safe_name = filename or (title or property_name).replace(" ", "_").replace(
            "/", "_"
        )
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)

    return fig
