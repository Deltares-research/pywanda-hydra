"""Post-processing extension protocols."""

from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

from .context import CaseContext, PostProcessingRunContext


@runtime_checkable
class CaseStep(Protocol):
    """Protocol for scenario-level post-processing step implementations."""

    name: ClassVar[str]

    def applicable(self, ctx: CaseContext) -> bool: ...

    def run(self, ctx: CaseContext) -> None: ...


@runtime_checkable
class RunStep(Protocol):
    """Protocol for run-level post-processing step implementations."""

    name: ClassVar[str]

    def run(self, ctx: PostProcessingRunContext) -> None: ...


@runtime_checkable
class PostProcessingWorkflow(Protocol):
    """Protocol for configurable post-processing workflows."""

    name: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]]

    def __init__(self, params: BaseModel) -> None: ...

    def case_steps(self, ctx: CaseContext) -> list[CaseStep]: ...

    def run_steps(self, ctx: PostProcessingRunContext) -> list[RunStep]: ...
