"""Post-processing step: Time plot generation."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from ..core.context import CaseContext
from ..plotting.renderers.theme import PlotTheme
from ..plotting.renderers.time_report_page import render_time_report_pages
from .route_plots import _build_report_meta

logger = logging.getLogger(__name__)


class TimePlotStep:
    """Renders time plots for each TimePlotSpecification in the scenario."""

    name = "time_plots"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only when time plots are defined and this step is enabled."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.time_plots) > 0

    def run(self, ctx: CaseContext) -> None:
        """Render all time plots to one consolidated per-case PDF."""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        figures_dir = ctx.case_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        case_id = ctx.case_dir.name
        case_pdf = figures_dir / f"{case_id}_tplots.pdf"
        with plt.ioff():
            meta = _build_report_meta(ctx)
            theme = PlotTheme()
            figures = render_time_report_pages(
                ctx.scenario.post_processing.time_plots,
                ctx.cache,
                report_meta_base=meta,
                theme=theme,
            )

            if not figures:
                logger.info(
                    "No time-plot figures rendered for case '%s'.",
                    ctx.case_dir.name,
                )
                return

            with PdfPages(case_pdf) as pdf:
                for fig in figures:
                    pdf.savefig(fig)
                    plt.close(fig)

        logger.info(
            "Rendered %d time plot(s) into %s for case '%s'.",
            len(figures),
            case_pdf,
            ctx.case_dir.name,
        )
