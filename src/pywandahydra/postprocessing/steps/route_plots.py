"""Post-processing step: Route plot generation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..context import CaseContext
from ..plotting.renderer import PlotTheme, ReportMeta, render_route_report_pages

logger = logging.getLogger(__name__)


class RoutePlotStep:
    """Renders route plots for each RoutePlotSpecification in the scenario."""

    name = "route_plots"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only when route plots are defined and this step is enabled."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.routes) > 0

    def run(self, ctx: CaseContext) -> None:
        """Render all route plots to one consolidated per-case PDF."""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        figures_dir = ctx.case_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        case_id = ctx.case_dir.name
        case_pdf = figures_dir / f"{case_id}.pdf"
        figures = []
        with plt.ioff():
            meta = _build_report_meta(ctx)
            theme = PlotTheme()
            figures = render_route_report_pages(
                ctx.scenario.post_processing.routes,
                ctx.cache,
                report_meta_base=meta,
                theme=theme,
            )

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


def _build_report_meta(ctx: CaseContext) -> ReportMeta:
    """Create report metadata from scenario and analysis metadata."""
    scen_meta = ctx.scenario.meta
    analysis_meta = ctx.scenario.analysis_meta

    report_date = _format_date(scen_meta.date)

    appendix = (scen_meta.appendix or "").strip()
    if appendix:
        base_figure_id = f"{appendix}.{int(scen_meta.number):03d}"
    else:
        base_figure_id = f"{ctx.case_dir.name}_"

    chapter = f"Chapter {scen_meta.chapter}" if scen_meta.chapter is not None else ""

    return ReportMeta(
        case_name=scen_meta.name,
        analysis_description=analysis_meta.analysis_description or "",
        scenario_description=scen_meta.description or scen_meta.extra or "",
        chapter=chapter,
        project_number=str(analysis_meta.project_number or ""),
        figure_id=base_figure_id,
        wanda_version=analysis_meta.wanda_version or "WANDA",
        report_date=report_date,
    )


def _format_date(value: Any) -> str:
    """Normalize scenario date metadata to dd-mm-YYYY text."""
    if value is None:
        return date.today().strftime("%d-%m-%Y")
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, date):
        return value.strftime("%d-%m-%Y")
    text = str(value).strip()
    if not text:
        return date.today().strftime("%d-%m-%Y")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return text
