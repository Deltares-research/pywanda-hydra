"""Run-level step: aggregate per-case tables into one run-level table."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..context import RunStepContext
from ..tables import aggregate_case_tables


class AggregateTablesStep:
    name = "aggregate_tables"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: RunStepContext) -> None:
        scenarios_dir = ctx.run_root / "scenarios"
        tables_dir = ctx.run_root / "tables"
        aggregate_case_tables(scenarios_dir, tables_dir, run_id=ctx.run_id)
