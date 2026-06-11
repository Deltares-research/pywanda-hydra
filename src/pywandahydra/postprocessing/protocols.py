"""Post-processing extension protocols."""

from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

from .context import CaseContext, RunStepContext


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

    def run(self, ctx: RunStepContext) -> None: ...


@runtime_checkable
class Methodology(Protocol):
    """Protocol for configurable post-processing methodologies."""

    name: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]]

    def __init__(self, params: BaseModel) -> None: ...

    def case_steps(self, ctx: CaseContext) -> list[CaseStep]: ...

    def run_steps(self, ctx: RunStepContext) -> list[RunStep]: ...
