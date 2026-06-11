"""Composable methodology driven by config-defined step lists."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..context import CaseContext, RunStepContext
from ..protocols import CaseStep, RunStep
from .base import StepSpec, build_case_step, build_run_step


class ComposedMethodology:
    """Methodology that builds its steps from declarative config."""

    name = "composed"
    description = "Compose case and run post-processing steps from configuration."

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        case_steps: list[StepSpec] = Field(default_factory=list)
        run_steps: list[StepSpec] = Field(default_factory=list)

    def __init__(self, params: BaseModel) -> None:
        self._p = self.Params.model_validate(params.model_dump())

    def case_steps(self, ctx: CaseContext) -> list[CaseStep]:
        del ctx
        return [build_case_step(spec) for spec in self._p.case_steps]

    def run_steps(self, ctx: RunStepContext) -> list[RunStep]:
        del ctx
        return [build_run_step(spec) for spec in self._p.run_steps]
