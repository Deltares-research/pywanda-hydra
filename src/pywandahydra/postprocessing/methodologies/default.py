"""Default configurable methodology implementation."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict

from ..context import CaseContext, RunStepContext
from ..protocols import CaseStep, RunStep
from ..steps.aggregate_tables import AggregateTablesStep
from ..steps.merge_pdfs import MergePdfsStep
from ..steps.route_plots import RoutePlotStep
from ..steps.summary_table import SummaryTableStep


class DefaultMethodology:
    """Standard post-processing: summary tables and route plots + run aggregation."""

    name = "default"
    description = "Standard post-processing pipeline (tables + route plots)."

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: BaseModel) -> None:
        self._p = params

    def case_steps(self, ctx: CaseContext) -> list[CaseStep]:
        del ctx
        return cast(list[CaseStep], [SummaryTableStep(), RoutePlotStep()])

    def run_steps(self, ctx: RunStepContext) -> list[RunStep]:
        del ctx
        return cast(list[RunStep], [AggregateTablesStep(), MergePdfsStep()])
