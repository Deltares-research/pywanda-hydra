"""Case-level PDF report assembly."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_pdf import PdfPages

from ..core.context import CaseContext
from ..plotting.renderers.report_page import ReportMeta
from .pdf_pages import PlotSpec, render_combined_report_pages
from .theme import PlotTheme

logger = logging.getLogger(__name__)


def render_case_pdf(ctx: CaseContext) -> Path | None:
    """Render configured route and time-series figures into the case PDF."""
    import matplotlib.pyplot as plt

    figures_dir = ctx.case_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    case_pdf = figures_dir / f"{ctx.case_dir.name}.pdf"
    specs: list[PlotSpec] = [
        *ctx.scenario.post_processing.figures.routes,
        *ctx.scenario.post_processing.figures.time_series,
    ]

    with plt.ioff():
        figures = render_combined_report_pages(
            specs,
            ctx.store,
            report_meta_base=build_report_meta(ctx),
            theme=PlotTheme(),
        )
        if not figures:
            logger.info("No plot figures rendered for case '%s'.", ctx.case_dir.name)
            return None
        with PdfPages(case_pdf) as pdf:
            for figure in figures:
                pdf.savefig(figure)
                plt.close(figure)

    logger.info(
        "Rendered %d figure(s) into %s for case '%s'.",
        len(figures),
        case_pdf,
        ctx.case_dir.name,
    )
    return case_pdf


def build_report_meta(ctx: CaseContext) -> ReportMeta:
    """Create report metadata from scenario and analysis metadata."""
    scenario = ctx.scenario
    report = scenario.post_processing.report
    analysis_meta = ctx.analysis_metadata
    appendix = (report.appendix or "").strip()
    base_figure_id = f"{appendix}.{int(scenario.number):03d}"
    if not appendix:
        base_figure_id = f"{ctx.case_dir.name}_"
    chapter = f"Chapter {report.chapter}" if report.chapter is not None else ""
    extra = scenario.extra_columns.get("Extra")
    scenario_description = report.description or (str(extra) if extra else "")
    return ReportMeta(
        case_name=scenario.name,
        analysis_description=analysis_meta.analysis_description or "",
        scenario_description=scenario_description,
        chapter=chapter,
        project_number=str(analysis_meta.project_number or ""),
        figure_id=base_figure_id,
        wanda_version=analysis_meta.wanda_version or "WANDA",
        report_date=_format_date(report.date),
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
    for format_string in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, format_string).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return text
