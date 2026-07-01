"""Report-style time-plot page renderer.

Renders TPlots-sheet specifications into the same A4 report layout used
for route plots: specifications sharing a ``fig`` value land on one page,
and within a page each distinct ``plot`` number becomes one stacked
subplot whose series are drawn together.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from ....scenarios.schema import TimePlotSpecification
from .common import apply_axis_spec, configure_matplotlib_defaults
from .theme import PlotTheme

logger = logging.getLogger(__name__)

configure_matplotlib_defaults()


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
    _warn_duplicate_axis_definitions(specs)
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


def _warn_duplicate_axis_definitions(specs: list[TimePlotSpecification]) -> None:
    """Warn when title/Xlabel/Ylabel are set on more than one spec in a subplot.

    Only the first spec's title and axis labels are used for a shared
    subplot; later definitions are ignored.
    """
    for field, get_value in (
        ("title", lambda s: s.title),
        ("Xlabel", lambda s: s.x_axis.label),
        ("Ylabel", lambda s: s.y_axis.label),
    ):
        defined = [s for s in specs if get_value(s) and get_value(s).strip()]
        if (
            len(defined) > 1
            and len(
                {get_value(s).strip() for s in defined if get_value(s) not in (None, "", "None")}
            )
            > 1
        ):
            logger.warning(
                "Multiple %s definitions for one subplot (%s); using the first "
                "(%s) and ignoring the rest.",
                field,
                [(s.component, s.property) for s in defined],
                get_value(defined[0]),
            )


def _select_columns(
    components: pd.DataFrame,
    spec: TimePlotSpecification,
) -> list[tuple[tuple[str, str, float], str]]:
    """Pick the cached columns matching a spec, honoring its ``location``.

    Returns ``(column, label)`` pairs. For pipes with multiple s-locations and
    no requested location, every location is plotted with an ``s=…`` label;
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
            return [(col, f"{spec.component} s={s_of(col):.1f} m")]
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
            out.append((col, f"{spec.component} s={s:.1f} m"))
        else:
            out.append((col, spec.component))
    return out
