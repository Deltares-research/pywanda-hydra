"""Post-processing step: Summary table export."""

from __future__ import annotations

import logging

from ..pipeline import PostProcessingContext, register_step
from ..plots.renderer import render_table

logger = logging.getLogger(__name__)


class SummaryTableStep:
    """Exports a per-case summary table (min/max per component/property)."""

    name = "summary_table"

    def applicable(self, ctx: PostProcessingContext) -> bool:
        """Run only if the scenario defines output specifications and the step is enabled."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.tables) > 0

    def run(self, ctx: PostProcessingContext) -> None:
        """Render the summary table to the case directory."""
        render_table(
            ctx.scenario.post_processing.tables,
            ctx.cache,
            output_dir=ctx.case_dir,
            export_props=ctx.export_table_props,
        )

        logger.info("Exported summary table for case '%s'.", ctx.case_dir.name)


# Auto-register on import
register_step(SummaryTableStep())
