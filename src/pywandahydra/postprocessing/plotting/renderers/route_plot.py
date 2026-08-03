"""Single route plot renderer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from ....results import ParquetResultStore, RouteIdentity
from ....scenarios import RoutePlotSpecification
from ...figures.export import savefig
from .common import apply_axis_spec, configure_matplotlib_defaults
from .theme import PlotTheme

logger = logging.getLogger(__name__)

configure_matplotlib_defaults()


def render_route_plot(
    spec: RoutePlotSpecification,
    store: ParquetResultStore,
    *,
    output_dir: Path | None = None,
    filename: str | None = None,
    export_props: dict[str, dict[str, Any]] | None = None,
    theme: PlotTheme | None = None,
) -> Figure | None:
    """Render a route plot from durable result data."""
    if theme is None:
        theme = PlotTheme()

    title = spec.title or f"{spec.route_id}_{spec.property}"
    data = store.read()
    route_data = data.routes.get(RouteIdentity(spec.route_id, spec.property)) if data else None
    envelope = route_data.envelope if route_data else None
    if envelope is None or envelope.empty:
        logger.warning("No cached envelope for route '%s' - skipping render.", title)
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

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

    apply_axis_spec(ax, spec.x_axis, axis="x")
    apply_axis_spec(ax, spec.y_axis, axis="y")
    if not spec.x_axis.label:
        ax.set_xlabel("s_location [m]")

    ax.set_title(title, fontfamily=theme.title_font)
    ax.legend(loc="best", fontsize=8, prop={"family": theme.legend_font})
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_dir:
        safe_name = filename or title.replace(" ", "_").replace("/", "_")
        savefig(fig, output_dir, safe_name, export_props=export_props, close=True)

    return fig

