"""Report-style route page renderer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ....scenarios.schema import RoutePlotSpecification
from ..styles.layout import PageMetadata
from .common import apply_axis_spec
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


def _create_content_axes(fig: Figure, count: int, theme: PlotTheme) -> list[Axes]:
    """Create vertically stacked content axes within the report frame."""
    if count <= 0:
        return []

    total_h = theme.content_top - theme.content_bottom
    total_gap = theme.row_gap * (count - 1)
    row_h = max((total_h - total_gap) / count, 0.08)

    axes: list[Axes] = []
    top = theme.content_top
    width = theme.content_right - theme.content_left

    for i in range(count):
        y0 = top - (i + 1) * row_h - i * theme.row_gap
        axes.append(fig.add_axes((theme.content_left, y0, width, row_h)))

    return axes


def _plot_route_series(
    ax: Axes,
    spec: RoutePlotSpecification,
    envelope: pd.DataFrame,
    route_data: dict[str, pd.DataFrame],
    theme: PlotTheme,
) -> None:
    """Render a single route subplot on an existing axes."""
    s_loc = np.asarray(envelope.index, dtype=float)
    sort_idx_s = np.argsort(s_loc)
    s_loc = s_loc[sort_idx_s]
    envelope = envelope.iloc[sort_idx_s]

    zero_s = _extract_time_zero_series(route_data)
    if zero_s is not None:
        ax.plot(
            zero_s.index.to_numpy(dtype=float),
            zero_s.to_numpy(dtype=float),
            label="0 s",
            color=theme.current_color,
            linewidth=1.2,
        )

    if "min" in envelope.columns:
        ax.plot(
            s_loc,
            envelope["min"],
            label="min",
            color=theme.min_color,
            linestyle=theme.min_linestyle,
            linewidth=1.2,
            zorder=-1,
        )
    if "max" in envelope.columns:
        ax.plot(
            s_loc,
            envelope["max"],
            label="max",
            color=theme.max_color,
            linestyle=theme.max_linestyle,
            linewidth=1.2,
            zorder=-1,
        )
    if {"min", "max"}.issubset(envelope.columns):
        ax.fill_between(
            s_loc, envelope["min"], envelope["max"], alpha=theme.envelope_alpha
        )

    if spec.property.strip().lower() == "head":
        s_prof, elev_prof = _extract_profile_series(route_data)
        if s_prof is not None and elev_prof is not None:
            ax.plot(
                s_prof,
                elev_prof,
                label="Elevation",
                color=theme.elevation_color,
                linewidth=theme.elevation_linewidth,
                alpha=theme.elevation_alpha,
                zorder=-2,
            )

    apply_axis_spec(ax, spec.x_axis, axis="x")
    apply_axis_spec(ax, spec.y_axis, axis="y")
    if not spec.x_axis.label:
        ax.set_xlabel("S-distance (m)")

    title = spec.title or f"{spec.route_id}_{spec.property}"
    ax.set_title(title, fontsize=theme.axis_title_size, fontfamily=theme.title_font)
    ax.grid(True, linestyle=theme.grid_linestyle, alpha=theme.grid_alpha)

    _annotate_route_endpoints(ax, route_data, theme)

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


def _extract_time_zero_series(route_data: dict[str, pd.DataFrame]) -> pd.Series | None:
    """Extract a 0 s series from cached route timeseries if available."""
    ts = route_data.get("timeseries")
    if ts is None or ts.empty:
        return None
    if not isinstance(ts.columns, pd.MultiIndex) or ts.columns.nlevels < 3:
        return None
    if len(ts.index) == 0:
        return None

    row0 = ts.iloc[0]
    s_vals: list[float] = []
    y_vals: list[float] = []
    for col, val in row0.items():
        try:
            s = float(col[2])
            y = float(val)
        except Exception:
            continue
        if np.isnan(s) or np.isnan(y):
            continue
        s_vals.append(s)
        y_vals.append(y)

    if not s_vals:
        return None

    ser = pd.Series(y_vals, index=pd.Index(s_vals, name="s_location [m]"))
    return ser.groupby(level=0).mean().sort_index()


def _annotate_route_endpoints(
    ax: Axes, route_data: dict[str, pd.DataFrame], theme: PlotTheme | None = None
) -> None:
    """Annotate start/end component labels from cached timeseries columns."""
    if theme is None:
        theme = PlotTheme()
    ts = route_data.get("timeseries")
    if (
        ts is None
        or ts.empty
        or not isinstance(ts.columns, pd.MultiIndex)
        or ts.columns.nlevels < 3
    ):
        return

    points: list[tuple[float, str]] = []
    for col in ts.columns:
        try:
            s = float(col[2])
        except Exception:
            continue
        if np.isnan(s):
            continue
        points.append((s, str(col[0])))

    if not points:
        return

    points.sort(key=lambda x: x[0])
    start_label = points[0][1]
    end_label = points[-1][1]

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    stepx = (xmax - xmin) * 0.05
    stepy = (ymax - ymin) * 0.05
    ax.text(xmin + stepx, ymin + stepy, start_label, fontfamily=theme.title_font)
    ax.text(xmax - 3 * stepx, ymin + stepy, end_label, fontfamily=theme.title_font)


def _extract_profile_series(
    route_data: dict[str, pd.DataFrame],
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Extract profile s/elevation arrays from cached route payload."""
    profile = route_data.get("profile")
    if profile is None or profile.empty or "elevation" not in profile.columns:
        return None, None

    s = np.asarray(profile.index, dtype=float)
    elev = np.asarray(profile["elevation"], dtype=float)
    if len(s) == 0 or len(s) != len(elev):
        return None, None

    sort_idx = np.argsort(s)
    return s[sort_idx], elev[sort_idx]


def _to_page_metadata(meta: ReportMeta, theme: PlotTheme) -> PageMetadata:
    """Map report metadata to the shared page layout schema."""
    case_description_lines = [
        x for x in (meta.scenario_description, meta.case_name) if x and x.strip()
    ]
    case_description = "\n".join(case_description_lines)

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
    """Parse known report date formats used in scenario metadata."""
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
