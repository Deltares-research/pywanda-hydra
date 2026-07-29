"""Example: Cross-scenario route comparison RunStep.

Reads Head and Pressure envelopes for a single route from the standard
Parquet cache and saves a 2-row comparison figure (one scenario per colour)
wrapped in the standard A4 Deltares report frame.

For the Head subplot the pipe elevation profile is overlaid as a single
themed line (same rendering as the per-case report pages).  Head and
elevation share the same y-axis (both in metres), which is standard for
hydraulic grade line (HGL) plots.

--- YAML workflow config ---

    execution:
      workflow:
        name: composed
        params:
          run_steps:
            - name: compare_route_scenarios
              params:
                case_ids: [case001, case002]
                route_head: "PS-1 to Plant - Head"
                route_pressure: "PS-1 to Plant - Pressure"
                output_filename: route_comparison
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from pydantic import BaseModel, ConfigDict, Field

from pywandahydra.postprocessing.core.context import PostProcessingRunContext
from pywandahydra.postprocessing.core.protocols import RunStep
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.plotting.renderers.report_page import (
    ReportMeta,
    _create_content_axes,
    _to_page_metadata,
)
from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme
from pywandahydra.postprocessing.plotting.styles.layout import draw_layout

logger = logging.getLogger(__name__)

_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]


class RouteComparisonStep(RunStep):
    """RunStep: compare route Head and Pressure envelopes across scenario cases.

    Produces a single 2-row PDF figure saved to the run figures directory.
    Row 1 shows the Head envelope (min/max) for each case with the pipe
    elevation profile overlaid; row 2 shows the Pressure envelope.
    Each case is rendered in a distinct colour with a shaded fill between
    min and max.
    """

    name: ClassVar[str] = "compare_route_scenarios"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        route_head: str = "PS-1 to Plant - Head"
        route_pressure: str = "PS-1 to Plant - Pressure"
        case_ids: list[str] = Field(default_factory=lambda: ["case001", "case002"])
        output_filename: str = "route_comparison"

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: PostProcessingRunContext) -> None:
        scenarios_dir = ctx.run_root / "scenarios"

        head_envs: list[tuple[str, pd.DataFrame]] = []
        head_profile: pd.DataFrame | None = None
        pressure_envs: list[tuple[str, pd.DataFrame]] = []

        for case_id in self._p.case_ids:
            cache = ParquetCache(scenarios_dir / case_id)

            head_data = cache.read_route(self._p.route_head)
            if "envelope" in head_data:
                head_envs.append((case_id, head_data["envelope"]))
                # Profile geometry is the same for every case; keep first one found.
                if head_profile is None and "profile" in head_data:
                    head_profile = head_data["profile"]
            else:
                logger.warning("No Head envelope for case '%s' – skipping.", case_id)

            pressure_data = cache.read_route(self._p.route_pressure)
            if "envelope" in pressure_data:
                pressure_envs.append((case_id, pressure_data["envelope"]))
            else:
                logger.warning("No Pressure envelope for case '%s' – skipping.", case_id)

        if not head_envs and not pressure_envs:
            logger.warning("No route data found for any case – figure skipped.")
            return

        meta = ReportMeta(
            case_name="Cross-scenario route comparison",
            analysis_description=", ".join(self._p.case_ids),
            scenario_description="Head and Pressure route envelopes",
            chapter="",
            project_number="",
            figure_id=self._p.output_filename,
            wanda_version="WANDA",
            report_date="",
        )

        with plt.ioff():
            fig = plt.figure(figsize=_THEME.figure_size)
            draw_layout(fig, _to_page_metadata(meta, _THEME))
            ax_head, ax_press = _create_content_axes(fig, 2, _THEME)

            _plot_envelope_row(
                ax_head,
                head_envs,
                ylabel="Head (m)",
                title=self._p.route_head,
                profile=head_profile,
            )
            _plot_envelope_row(
                ax_press,
                pressure_envs,
                ylabel="Pressure (bar)",
                title=self._p.route_pressure,
                xlabel="s-distance (m)",
            )

            figures_dir = ctx.run_root / "figures"
            figures_dir.mkdir(parents=True, exist_ok=True)
            output_path = figures_dir / f"{self._p.output_filename}.pdf"
            with PdfPages(output_path) as pdf:
                pdf.savefig(fig)
            plt.close(fig)

        logger.info("Saved route comparison to %s", output_path)


def _plot_envelope_row(
    ax: plt.Axes,
    envs: list[tuple[str, pd.DataFrame]],
    *,
    ylabel: str,
    title: str,
    xlabel: str = "",
    profile: pd.DataFrame | None = None,
) -> None:
    for i, (case_id, env) in enumerate(envs):
        color = _COLORS[i % len(_COLORS)]
        s = env.index.astype(float)
        ax.fill_between(s, env["min"], env["max"], alpha=0.25, color=color)
        ax.plot(s, env["max"], color=color, linewidth=1.2, label=f"{case_id} max")
        ax.plot(s, env["min"], color=color, linewidth=1.2, linestyle="--", label=f"{case_id} min")

    if profile is not None and not profile.empty and "elevation" in profile.columns:
        _plot_elevation_profile(ax, profile)

    ax.autoscale(tight=True, axis="x")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)


_THEME = PlotTheme()


def _plot_elevation_profile(ax: plt.Axes, profile: pd.DataFrame) -> None:
    """Overlay the pipe elevation profile using the default plot theme."""
    s = profile.index.astype(float)
    elev = profile["elevation"].astype(float)
    ax.plot(
        s,
        elev,
        label="Elevation",
        color=_THEME.elevation_color,
        linewidth=_THEME.elevation_linewidth,
        alpha=_THEME.elevation_alpha,
        zorder=-2,
    )


def main() -> None:
    """Run the comparison step against the bundled example data."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    run_root = Path(__file__).parent / "data" / "runs" / "example_run"

    step = RouteComparisonStep(
        RouteComparisonStep.Params(
            case_ids=["case001", "case002"],
            route_head="PS-1 to Plant - Head",
            route_pressure="PS-1 to Plant - Pressure",
            output_filename="route_comparison",
        )
    )

    ctx = PostProcessingRunContext(
        run_root=run_root,
        run_id="example_run",
        case_results=(),
    )

    step.run(ctx)
    print(f"Figure saved to: {run_root / 'figures' / 'route_comparison.pdf'}")


if __name__ == "__main__":
    main()
