"""Default configurable workflow implementation."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict

from ..core.context import CaseContext, PostProcessingRunContext
from ..core.protocols import CaseStep, RunStep
from ..steps.aggregate_tables import AggregateTablesStep
from ..steps.merge_pdfs import MergePdfsStep
from ..steps.route_plots import RoutePlotStep
from ..steps.summary_table import SummaryTableStep
from ..steps.time_plots import TimePlotStep


class DefaultWorkflow:
    """Standard post-processing: summary tables, route and time plots + run aggregation."""

    name = "default"
    description = "Standard post-processing pipeline (tables + route/time plots)."

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: BaseModel) -> None:
        self._p = params

    def case_steps(self, ctx: CaseContext) -> list[CaseStep]:
        del ctx
        return cast(
            list[CaseStep], [SummaryTableStep(), RoutePlotStep(), TimePlotStep()]
        )

    def run_steps(self, ctx: PostProcessingRunContext) -> list[RunStep]:
        del ctx
        return cast(list[RunStep], [AggregateTablesStep(), MergePdfsStep()])
