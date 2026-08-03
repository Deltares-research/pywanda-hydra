"""Post-processing step: Summary table export."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from ..core.context import CaseContext
from ..reports.tables import render_summary_table

logger = logging.getLogger(__name__)


class SummaryTableStep:
    """Exports a per-case summary table (min/max per component/property)."""

    name = "summary_table"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only if the scenario defines output specifications."""
        pp = ctx.scenario.post_processing
        return len(pp.tables.minmax) > 0

    def run(self, ctx: CaseContext) -> None:
        """Render the summary table to the case directory."""
        render_summary_table(
            ctx.scenario.post_processing.tables.minmax,
            ctx.store,
            output_dir=ctx.case_dir,
            export_props=ctx.export_table_props,
        )

        logger.info("Exported summary table for case '%s'.", ctx.case_dir.name)
