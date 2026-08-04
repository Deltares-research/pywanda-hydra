"""Time-series figure rendering from durable result data."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from pywandahydra.scenarios.models.plot_axis import AxisSpecification

from ...results import ParquetResultStore
from .axes import apply_axis_spec, configure_matplotlib_defaults
from .export import savefig
from .theme import PlotTheme

logger = logging.getLogger(__name__)

configure_matplotlib_defaults()


def render_time_series_plot(
    components: list[str],
    property_name: str,
    store: ParquetResultStore,
    *,
    title: str | None = None,
    x_axis: AxisSpecification | None = None,
    y_axis: AxisSpecification | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
    export_props: dict[str, dict[str, Any]] | None = None,
    theme: PlotTheme | None = None,
) -> Figure | None:
    """Render a time-series plot from durable component data."""
    theme = theme or PlotTheme()
    data = store.read()
    frame = data.components.data if data else pd.DataFrame()
    if frame.empty:
        logger.warning("No cached component data - skipping time series render.")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = False
    for component in components:
        if isinstance(frame.columns, pd.MultiIndex):
            matching = [
                column
                for column in frame.columns
                if column[0] == component and column[1] == property_name
            ]
            for column in matching:
                has_location = (
                    len(column) >= 3 and isinstance(column[2], float) and not math.isnan(column[2])
                )
                if has_location:
                    label = f"{column[0]} s={column[2]:.1f} m"
                else:
                    label = column[0]
                ax.plot(frame.index, frame[column], label=label)
                plotted = True
        else:
            column_name = f"{component}|{property_name}"
            if column_name in frame.columns:
                ax.plot(frame.index, frame[column_name], label=component)
                plotted = True

    if not plotted:
        logger.warning("No matching data for components=%s, property=%s", components, property_name)
        plt.close(fig)
        return None
    if x_axis:
        apply_axis_spec(ax, x_axis, axis="x")
    else:
        ax.set_xlabel("Time [s]")
    if y_axis:
        apply_axis_spec(ax, y_axis, axis="y")
    ax.set_title(title or property_name, fontfamily=theme.title_font)
    ax.legend(loc="best", fontsize=8, prop={"family": theme.legend_font})
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_dir:
        safe_name = filename or (title or property_name).replace(" ", "_").replace("/", "_")
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)
    return fig
