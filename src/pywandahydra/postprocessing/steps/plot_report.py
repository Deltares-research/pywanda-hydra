"""Post-processing step: combined route/time plot report generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..core.context import CaseContext
from ..figures.case_pdf import render_case_pdf


class PlotReportStep:
    """Renders route and time plots into one consolidated per-case PDF."""

    name = "plot_report"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only when route or time plots are defined."""
        pp = ctx.scenario.post_processing
        return len(pp.figures.routes) > 0 or len(pp.figures.time_series) > 0

    def run(self, ctx: CaseContext) -> None:
        """Render all route and time plots to one consolidated per-case PDF."""
        render_case_pdf(ctx)
