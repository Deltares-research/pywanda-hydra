"""Post-processing step: Route plot generation."""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from ..pipeline import PostProcessingContext, register_step
from ..plots.renderer import render_route_plot

logger = logging.getLogger(__name__)


class RoutePlotStep:
    """Renders route plots for each RoutePlotSpecification in the scenario."""

    name = "route_plots"

    def applicable(self, ctx: PostProcessingContext) -> bool:
        """Run only when route plots are defined and this step is enabled."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.routes) > 0

    def run(self, ctx: PostProcessingContext) -> None:
        """Render all route plots to one consolidated per-case PDF."""
        figures_dir = ctx.case_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        case_id = ctx.case_dir.name
        case_pdf = figures_dir / f"{case_id}.pdf"
        figures = []
        with plt.ioff():
            for spec in ctx.scenario.post_processing.routes:
                fig = render_route_plot(spec, ctx.cache)
                if fig is not None:
                    figures.append(fig)

            if not figures:
                logger.info(
                    "No route figures rendered for case '%s'.",
                    ctx.case_dir.name,
                )
                return

            with PdfPages(case_pdf) as pdf:
                for fig in figures:
                    pdf.savefig(fig)
                    plt.close(fig)

        logger.info(
            "Rendered %d route plot(s) into %s for case '%s'.",
            len(figures),
            case_pdf,
            ctx.case_dir.name,
        )


# Auto-register on import
register_step(RoutePlotStep())
