"""Example: Space-time plot CaseStep.

Reads the route timeseries from the standard Parquet cache (time Ã— s-location)
and renders a 2-D pcolormesh figure per case showing a hydraulic property as a
function of both position along the route and simulation time.

The built-in extraction writes a
``timeseries.parquet`` for every route plot defined in the scenario.

Route selection
---------------
By default the step derives the set of routes to plot from the scenario
specification (i.e. what was defined in the *RPlots* sheet of the cases XLS).
Two optional parameters let you narrow or override this:

``properties``
    Filter to only routes whose property matches one of the listed names,
    e.g. ``["Pressure"]`` to skip Head routes.  Case-insensitive.
    When omitted all properties from the scenario are included.

``route_titles``
    Explicit list of route titles (the cache key, e.g.
    ``"PS-1 to Plant - Pressure"``).  When set, ``properties`` is ignored
    and only these titles are plotted â€” regardless of what is in the scenario.
    Useful when running the step directly from Python or when you want a
    fixed set of plots independent of the XLS.

--- YAML: all routes from scenario, Pressure only ---

    execution:
      workflow:
        name: composed
        params:
          case_steps:
            - name: space_time_plot
              params:
                properties: [Pressure]
                colormap: RdBu_r

--- YAML: explicit titles, ignore scenario ---

    execution:
      workflow:
        name: composed
        params:
          case_steps:
            - name: space_time_plot
              params:
                route_titles:
                  - "PS-1 to Plant - Pressure"
                  - "PS-2 to Plant - Pressure"

Grid resampling
---------------
``resample_factor``
    Multiplier applied to both the time and s-location axes before rendering.
    Values **< 1** reduce the number of grid points (e.g. ``0.25`` quarters the
    resolution, keeping PDF file sizes manageable for A3/poster prints).
    Values **> 1** upsample the grid via the chosen interpolation method,
    producing smoother colour gradients at the cost of a slightly larger file.
    ``None`` (default) leaves the simulation grid unchanged.

``resample_method``
    Scipy interpolation method: ``"linear"`` (default, fast), ``"cubic"``
    (smooth, good for upsampling), or ``"nearest"`` (preserves exact values,
    useful for sanity checks).  Ignored when ``resample_factor`` is ``None``.

--- YAML: downsample for A3 print (factor 0.25) ---

    execution:
      workflow:
        name: composed
        params:
          case_steps:
            - name: space_time_plot
              params:
                properties: [Pressure]
                resample_factor: 0.25

--- YAML: upsample for smoother contours ---

    execution:
      workflow:
        name: composed
        params:
          case_steps:
            - name: space_time_plot
              params:
                properties: [Pressure]
                resample_factor: 3.0
                resample_method: cubic
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import ClassVar

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import scipy.interpolate as sci
from matplotlib.backends.backend_pdf import PdfPages
from pydantic import BaseModel, ConfigDict, Field

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.core.protocols import CaseStep
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.plotting.renderers.report_page import (
    _create_content_axes,
    _to_page_metadata,
)
from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme
from pywandahydra.postprocessing.plotting.styles.layout import draw_layout
from pywandahydra.postprocessing.steps.report_meta import build_report_meta
from pywandahydra.scenarios import ScenarioSpecification

logger = logging.getLogger(__name__)

_THEME = PlotTheme()


def _resample_grid(
    times: np.ndarray,
    s_locs: np.ndarray,
    Z: np.ndarray,
    factor: float,
    method: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resample the space-time grid by *factor* using scipy interpolation.

    factor < 1 reduces resolution (smaller PDF, faster render).
    factor > 1 upsamples for smoother colour gradients.
    """
    # Sort times and s_locs, reorder Z accordingly.
    t_sort_idx = np.argsort(times)
    times = times[t_sort_idx]
    Z = Z[t_sort_idx, :]

    s_sort_idx = np.argsort(s_locs)
    s_locs = s_locs[s_sort_idx]
    Z = Z[:, s_sort_idx]

    # Remove duplicate coordinate values.
    _, t_unique_idx = np.unique(times, return_index=True)
    t_unique_idx = np.sort(t_unique_idx)  # Restore original order
    times = times[t_unique_idx]
    Z = Z[t_unique_idx, :]

    _, s_unique_idx = np.unique(s_locs, return_index=True)
    s_unique_idx = np.sort(s_unique_idx)  # Restore original order
    s_locs = s_locs[s_unique_idx]
    Z = Z[:, s_unique_idx]

    n_t = max(2, round(len(times) * factor))
    n_s = max(2, round(len(s_locs) * factor))
    t_new = np.linspace(times[0], times[-1], n_t)
    s_new = np.linspace(s_locs[0], s_locs[-1], n_s)
    interp = sci.RegularGridInterpolator(
        (times, s_locs), Z, method=method, bounds_error=False, fill_value=None
    )
    tt, ss = np.meshgrid(t_new, s_new, indexing="ij")
    # Flatten meshgrid to a list of (t, s) points, evaluate, then reshape
    points = np.stack([tt.ravel(), ss.ravel()], axis=1)
    Z_interp = interp(points).reshape(tt.shape)
    return t_new, s_new, Z_interp


def _shift_cmap(
    cmap_name: str,
    vmin: float,
    vmax: float,
    vcenter: float | None,
) -> mcolors.Colormap:
    """Return a resampled colormap whose midpoint colour sits at vcenter.

    With a plain linear norm the diverging centre would land at 0.5 in
    colormap space only when the data range is symmetric.  This function
    remaps the lookup table so the midpoint of the source colormap aligns
    with ``(vcenter - vmin) / (vmax - vmin)``, keeping tick spacing linear.
    When vcenter is None the original colormap is returned unchanged.
    """
    base = plt.get_cmap(cmap_name)
    if vcenter is None:
        return base

    pivot = float(np.clip((vcenter - vmin) / (vmax - vmin), 1e-6, 1 - 1e-6))
    n = 512
    xs = np.linspace(0.0, 1.0, n)
    # Map linear positions to colormap fractions: compress/expand each half.
    cmap_fracs = np.where(xs <= pivot, xs / pivot * 0.5, 0.5 + (xs - pivot) / (1.0 - pivot) * 0.5)
    colors = base(cmap_fracs)
    return mcolors.LinearSegmentedColormap.from_list(f"{cmap_name}_shifted", colors, N=n)


def _annotate_pipe_boundaries_mesh(
    ax: plt.Axes,
    route_data: dict,
    theme: PlotTheme,
) -> None:
    """Draw pipe boundary lines and labels on a pcolormesh axes.

    Same logic as report_page._annotate_pipe_boundaries but with zorder=3 so
    the dashed lines render above the pcolormesh collection (zorder ~1).
    """
    import pandas as pd

    ts = route_data.get("timeseries")
    if (
        ts is None
        or ts.empty
        or not isinstance(ts.columns, pd.MultiIndex)
        or ts.columns.nlevels < 3
    ):
        return

    ranges: dict[str, tuple[float, float]] = {}
    for col in ts.columns:
        try:
            s = float(col[2])
        except Exception:
            continue
        if np.isnan(s):
            continue
        name = str(col[0])
        if name not in ranges:
            ranges[name] = (s, s)
        else:
            lo, hi = ranges[name]
            ranges[name] = (min(lo, s), max(hi, s))

    if not ranges:
        return

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    y_text = ymax - (ymax - ymin) * 0.02

    boundary_locations = {s for lo, hi in ranges.values() for s in (lo, hi)}
    for s in boundary_locations:
        if xmin < s < xmax:
            ax.axvline(x=s, color="black", linestyle="--", alpha=0.5, linewidth=1.0, zorder=3)

    for name, (lo, hi) in ranges.items():
        mid = (lo + hi) / 2
        ax.text(
            mid,
            y_text,
            name,
            va="top",
            ha="center",
            clip_on=True,
            fontsize=theme.legend_fontsize,
            fontfamily=theme.title_font,
            zorder=4,
        )


class SpaceTimePlotStep(CaseStep):
    """CaseStep: render space-time pcolormesh figures from cached route timeseries.

    The timeseries DataFrame has time steps as its index and a MultiIndex
    ``(component, property, s_location)`` as its columns.  The ``s_location``
    level gives the cumulative distance along the route in metres.

    Route selection (in order of priority):

    1. ``route_titles`` â€” explicit list; skips scenario lookup entirely.
    2. ``properties`` filter applied to ``ctx.scenario.post_processing.routes``.
    3. All routes in the scenario (default, both params omitted).
    """

    name: ClassVar[str] = "space_time_plot"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        route_titles: list[str] | None = Field(
            default=None,
            description=(
                "Explicit route titles to plot. When set, the scenario route list "
                "and `properties` filter are ignored."
            ),
        )
        properties: list[str] | None = Field(
            default=None,
            description=(
                "Only plot routes whose property matches one of these names "
                "(case-insensitive). Ignored when `route_titles` is set."
            ),
        )
        colormap: str = "RdBu_r"
        vmin: float | None = Field(
            default=None, description="Colormap lower bound. Defaults to data minimum."
        )
        vmax: float | None = Field(
            default=None, description="Colormap upper bound. Defaults to data maximum."
        )
        vcenter: float | None = Field(
            default=None,
            description=(
                "When set, centres the colormap on this value using TwoSlopeNorm â€” "
                "vmin and vmax need not be symmetric. Set to 0 for pressure plots."
            ),
        )
        resample_factor: float | None = Field(
            default=None,
            description=(
                "Grid resampling factor applied before rendering. "
                "< 1 reduces the number of grid points (e.g. 0.25 for print-size PDFs); "
                "> 1 upsamples for smoother colour gradients. "
                "None leaves the simulation grid unchanged."
            ),
        )
        resample_method: str = Field(
            default="linear",
            description=(
                "Scipy interpolation method used when resample_factor is set: "
                "'linear' (default), 'cubic' (smooth, good for upsampling), "
                "or 'nearest' (preserves exact values)."
            ),
        )

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        return bool(ctx.scenario.post_processing.figures.routes) or bool(ctx.cache.list_routes())

    def run(self, ctx: CaseContext) -> None:
        titles = self._resolve_titles(ctx)
        if not titles:
            logger.warning(
                "No routes to plot for case '%s' â€“ check route_titles / properties params "
                "and the scenario RPlots sheet.",
                ctx.case_dir.name,
            )
            return
        for title in titles:
            self._plot_route(ctx, title)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_titles(self, ctx: CaseContext) -> list[str]:
        """Return the ordered list of route titles to plot for this case."""
        if self._p.route_titles is not None:
            return list(self._p.route_titles)

        specs = ctx.scenario.post_processing.figures.routes
        if self._p.properties is not None:
            allowed = {p.lower() for p in self._p.properties}
            specs = [s for s in specs if s.property.lower() in allowed]

        return [s.title or f"{s.route_id}_{s.property}" for s in specs]

    def _plot_route(self, ctx: CaseContext, title: str) -> None:
        route_data = ctx.cache.read_route(title)
        ts = route_data.get("timeseries")
        if ts is None or ts.empty:
            logger.warning(
                "No timeseries data for route '%s' in case '%s' â€“ skipping.",
                title,
                ctx.case_dir.name,
            )
            return

        # columns: MultiIndex (component, property, s_location)
        s_locs = ts.columns.get_level_values("s_location").astype(float)
        times = ts.index.astype(float)
        Z = ts.values  # shape: (n_times, n_s)

        if self._p.resample_factor is not None:
            times, s_locs, Z = _resample_grid(
                times, s_locs, Z, self._p.resample_factor, self._p.resample_method
            )

        # Infer colorbar label from the property level (all columns share one property)
        prop_label = ts.columns.get_level_values("property")[0]

        vmin = self._p.vmin if self._p.vmin is not None else float(np.nanmin(Z))
        vmax = self._p.vmax if self._p.vmax is not None else float(np.nanmax(Z))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
            vmin = vmin if np.isfinite(vmin) else 0.0
            vmax = max(vmax if np.isfinite(vmax) else 1.0, vmin + 1.0)

        # Build a linear norm + a colormap shifted so the diverging centre colour
        # sits at vcenter's actual linear position in [vmin, vmax].  This keeps
        # tick spacing uniform (no TwoSlopeNorm stretching) while still placing
        # the neutral colour at the correct data value.
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        cmap = _shift_cmap(self._p.colormap, vmin, vmax, self._p.vcenter)

        with plt.ioff():
            base_meta = build_report_meta(ctx)
            meta = dataclasses.replace(base_meta, figure_id=f"{base_meta.figure_id}{title}")
            fig = plt.figure(figsize=_THEME.figure_size)
            draw_layout(fig, _to_page_metadata(meta, _THEME))
            (ax,) = _create_content_axes(fig, 1, _THEME)

            pcm = ax.pcolormesh(
                s_locs, times, Z, cmap=cmap, norm=norm, shading="auto", rasterized=True
            )

            # Place the colorbar in an explicit axes so it matches the content
            # axes height rather than stretching to the full figure.
            ax_pos = ax.get_position()
            cbar_ax = fig.add_axes(
                (
                    ax_pos.x1 + 0.015,
                    ax_pos.y0,
                    0.022,
                    ax_pos.height,
                )
            )
            cbar = fig.colorbar(pcm, cax=cbar_ax)
            cbar.set_label(prop_label, rotation=270, labelpad=14)

            # Ensure vmin, vmax, and vcenter (if set) all appear as ticks.
            ticks: set[float] = {t for t in cbar.get_ticks().tolist() if vmin <= t <= vmax}
            ticks.update([vmin, vmax])
            if self._p.vcenter is not None:
                ticks.add(float(np.clip(self._p.vcenter, vmin, vmax)))
            cbar.set_ticks(sorted(ticks))

            ax.set_xlabel("s-distance (m)")
            ax.set_ylabel("Time (s)")
            ax.set_title(f"{title} â€” {ctx.scenario.name}", fontsize=_THEME.axis_title_size)
            ax.autoscale(tight=True, axis="x")
            _annotate_pipe_boundaries_mesh(ax, route_data, _THEME)

            stem = title.replace(" ", "_").replace("/", "_") + "_space_time"
            figures_dir = ctx.case_dir / "figures"
            figures_dir.mkdir(parents=True, exist_ok=True)
            output_path = figures_dir / f"{stem}.pdf"

            with PdfPages(output_path) as pdf:
                pdf.savefig(fig)
            plt.close(fig)

        logger.info("Saved space-time plot to %s", output_path)


def _load_case_context(case_dir: Path, case_number: int) -> CaseContext:
    """Build a minimal CaseContext from a case directory on disk."""
    case_id = case_dir.name
    state_path = case_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        case_id = state.get("case_id", case_id)

    scenario = ScenarioSpecification(number=case_number, include=True, name=case_id)
    return CaseContext(cache=ParquetCache(case_dir), scenario=scenario, case_dir=case_dir)


def main() -> None:
    """Run the space-time plot step across all cases in the bundled example data."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    scenarios_dir = Path(__file__).parent / "data" / "runs" / "example_run" / "scenarios"

    # Standalone example: use explicit titles since the minimal CaseContext
    # built by _load_case_context() has no scenario route specs.
    # For different bounds or other properties, include another step instance
    # with different Params in the list
    step = [
        SpaceTimePlotStep(
            SpaceTimePlotStep.Params(
                route_titles=[
                    "PS-1 to Plant - Pressure",
                    "PS-2 to Plant - Pressure",
                ],
                vmin=-1.0,
                vmax=+10.0,
                vcenter=0.0,
                resample_factor=2.0,  # < 1 for smaller PDF, > 1 for smoother gradients
                resample_method="cubic",  # ignored when resample_factor is None
            )
        )
    ]

    for i, case_dir in enumerate(sorted(scenarios_dir.iterdir()), start=1):
        if not case_dir.is_dir():
            continue
        ctx = _load_case_context(case_dir, case_number=i)
        for s in step:
            if s.applicable(ctx):
                s.run(ctx)
                print(f"Space-time plots written for {case_dir.name}")
            else:
                print(f"Skipping {case_dir.name}: no cached routes.")


if __name__ == "__main__":
    main()

