"""Post-processing step: combined route/time plot report generation."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from ..core.context import CaseContext
from ..plotting.renderers.combined_report import PlotSpec, render_combined_report_pages
from ..plotting.renderers.theme import PlotTheme
from .report_meta import build_report_meta

logger = logging.getLogger(__name__)


class PlotReportStep:
    """Renders route and time plots into one consolidated per-case PDF."""

    name = "plot_report"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only when route or time plots are defined and this step is enabled."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.routes) > 0 or len(pp.time_plots) > 0

    def run(self, ctx: CaseContext) -> None:
        """Render all route and time plots to one consolidated per-case PDF."""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        figures_dir = ctx.case_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        case_id = ctx.case_dir.name
        case_pdf = figures_dir / f"{case_id}.pdf"

        specs: list[PlotSpec] = [
            *ctx.scenario.post_processing.routes,
            *ctx.scenario.post_processing.time_plots,
        ]

        with plt.ioff():
            meta = build_report_meta(ctx)
            theme = PlotTheme()
            figures = render_combined_report_pages(
                specs,
                ctx.cache,
                report_meta_base=meta,
                theme=theme,
            )

            if not figures:
                logger.info(
                    "No plot figures rendered for case '%s'.",
                    ctx.case_dir.name,
                )
                return

            with PdfPages(case_pdf) as pdf:
                for fig in figures:
                    pdf.savefig(fig)
                    plt.close(fig)

        logger.info(
            "Rendered %d figure(s) into %s for case '%s'.",
            len(figures),
            case_pdf,
            ctx.case_dir.name,
        )
