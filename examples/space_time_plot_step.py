"""Example: Space-time plot CaseStep.

Reads the route timeseries from the standard Parquet cache (time × s-location)
and renders a 2-D pcolormesh figure per case showing a hydraulic property as a
function of both position along the route and simulation time.

No custom extractor is required: the standard extraction already writes a
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
    and only these titles are plotted — regardless of what is in the scenario.
    Useful when running the step standalone from Python or when you want a
    fixed set of plots independent of the XLS.

--- Plugin registration (pyproject.toml) ---

    [project.entry-points."pywandahydra.case_steps"]
    space_time_plot = "my_plugin.steps:SpaceTimePlotStep"

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
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import ClassVar

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pydantic import BaseModel, ConfigDict, Field

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification

logger = logging.getLogger(__name__)


class SpaceTimePlotStep:
    """CaseStep: render space-time pcolormesh figures from cached route timeseries.

    The timeseries DataFrame has time steps as its index and a MultiIndex
    ``(component, property, s_location)`` as its columns.  The ``s_location``
    level gives the cumulative distance along the route in metres.

    Route selection (in order of priority):

    1. ``route_titles`` — explicit list; skips scenario lookup entirely.
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

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        return bool(ctx.scenario.post_processing.routes) or bool(ctx.cache.list_routes())

    def run(self, ctx: CaseContext) -> None:
        titles = self._resolve_titles(ctx)
        if not titles:
            logger.warning(
                "No routes to plot for case '%s' – check route_titles / properties params "
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

        specs = ctx.scenario.post_processing.routes
        if self._p.properties is not None:
            allowed = {p.lower() for p in self._p.properties}
            specs = [s for s in specs if s.property.lower() in allowed]

        return [s.title or f"{s.route_id}_{s.property}" for s in specs]

    def _plot_route(self, ctx: CaseContext, title: str) -> None:
        route_data = ctx.cache.read_route(title)
        ts = route_data.get("timeseries")
        if ts is None or ts.empty:
            logger.warning(
                "No timeseries data for route '%s' in case '%s' – skipping.",
                title,
                ctx.case_dir.name,
            )
            return

        # columns: MultiIndex (component, property, s_location)
        s_locs = ts.columns.get_level_values("s_location").astype(float)
        times = ts.index.astype(float)
        Z = ts.values  # shape: (n_times, n_s)

        # Infer colorbar label from the property level (all columns share one property)
        prop_label = ts.columns.get_level_values("property")[0]

        with plt.ioff():
            fig, ax = plt.subplots(figsize=(12, 5))
            pcm = ax.pcolormesh(s_locs, times, Z, cmap=self._p.colormap, shading="auto")
            cbar = fig.colorbar(pcm, ax=ax)
            cbar.set_label(prop_label)

            ax.set_xlabel("s-distance (m)")
            ax.set_ylabel("Time (s)")
            ax.set_title(f"{title} — {ctx.scenario.meta.name}")

            stem = title.replace(" ", "_").replace("/", "_") + "_space_time"
            figures_dir = ctx.case_dir / "figures"
            figures_dir.mkdir(parents=True, exist_ok=True)
            output_path = figures_dir / f"{stem}.pdf"

            with PdfPages(output_path) as pdf:
                pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        logger.info("Saved space-time plot to %s", output_path)


def _load_case_context(case_dir: Path, case_number: int) -> CaseContext:
    """Build a minimal CaseContext from a case directory on disk."""
    case_id = case_dir.name
    state_path = case_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        case_id = state.get("case_id", case_id)

    scenario = ScenarioSpecification(
        meta=ScenarioMeta.model_validate({"Number": case_number, "Include": True, "Name": case_id})
    )
    return CaseContext(cache=ParquetCache(case_dir), scenario=scenario, case_dir=case_dir)


def main() -> None:
    """Run the space-time plot step across all cases in the bundled example data."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    scenarios_dir = Path(__file__).parent / "data" / "runs" / "example_run" / "scenarios"

    # Standalone example: use explicit titles since the minimal CaseContext
    # built by _load_case_context() has no scenario route specs.
    step = SpaceTimePlotStep(
        SpaceTimePlotStep.Params(
            route_titles=[
                "PS-1 to Plant - Pressure",
                "PS-2 to Plant - Pressure",
            ]
        )
    )

    for i, case_dir in enumerate(sorted(scenarios_dir.iterdir()), start=1):
        if not case_dir.is_dir():
            continue
        ctx = _load_case_context(case_dir, case_number=i)
        if step.applicable(ctx):
            step.run(ctx)
            print(f"Space-time plots written for {case_dir.name}")
        else:
            print(f"Skipping {case_dir.name}: no cached routes.")


if __name__ == "__main__":
    main()
