"""Shared report-metadata helper for plot-rendering steps."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..core.context import CaseContext
from ..plotting.renderers.report_page import ReportMeta


def build_report_meta(ctx: CaseContext) -> ReportMeta:
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
