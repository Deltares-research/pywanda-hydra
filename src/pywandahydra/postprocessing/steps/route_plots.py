"""Post-processing step: Route plot generation."""

from __future__ import annotations

import logging

from ..pipeline import PostProcessingContext, register_step
from ..plots.renderer import render_route_plot

logger = logging.getLogger(__name__)


class RoutePlotStep:
    """Renders route plots for each RoutePlotSpecification in the scenario."""

    name = "route_plots"

    def applicable(self, ctx: PostProcessingContext) -> bool:
        """Run only if the scenario defines route plot specifications."""
        return len(ctx.scenario.route_plots) > 0

    def run(self, ctx: PostProcessingContext) -> None:
        """Render all route plots to the per-case figures directory."""
        figures_dir = ctx.case_dir / "figures"
        case_id = ctx.case_dir.name

        for index, spec in enumerate(ctx.scenario.route_plots):
            stem = case_id if index == 0 else f"{case_id}_{index:03d}"
            render_route_plot(
                spec,
                ctx.cache,
                output_dir=figures_dir,
                filename=stem,
                export_props=ctx.export_figure_props,
            )

        logger.info(
            "Rendered %d route plot(s) for case '%s'.",
            len(ctx.scenario.route_plots),
            ctx.case_dir.name,
        )


# Auto-register on import
register_step(RoutePlotStep())
