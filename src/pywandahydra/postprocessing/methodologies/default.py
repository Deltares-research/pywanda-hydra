"""Default methodology — runs all registered pipeline steps.

This replicates the existing behaviour: execute summary_table and
route_plots steps in order. Serves as the baseline methodology and
as a template for writing new ones.
"""

from __future__ import annotations

from ..pipeline import PostProcessingContext, PostProcessor
from ..steps.route_plots import RoutePlotStep
from ..steps.summary_table import SummaryTableStep


class DefaultMethodology:
    """Standard post-processing: summary tables then route plots."""

    name = "default"
    description = "Standard post-processing pipeline (tables + route plots)."

    def get_steps(self, ctx: PostProcessingContext) -> list[PostProcessor]:
        """Return the default step sequence."""
        return [
            SummaryTableStep(),
            RoutePlotStep(),
        ]
