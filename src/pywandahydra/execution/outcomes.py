"""Immutable outcomes returned by case and run execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..postprocessing.pipeline import PostProcessingOutcome


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Outcome from simulating, post-processing, or skipping one case."""

    case_id: str
    action: Literal["simulate", "postprocess", "skip"]
    success: bool
    duration_s: float | None = None
    error: str | None = None
    post_processing: tuple[PostProcessingOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class RunResult:
    """Aggregate result with counts derived from immutable case outcomes."""

    run_id: str
    cases: tuple[CaseResult, ...]
    post_processing: tuple[PostProcessingOutcome, ...] = ()

    @property
    def n_success(self) -> int:
        return sum(case.success and case.action != "skip" for case in self.cases)

    @property
    def n_failed(self) -> int:
        return sum(not case.success for case in self.cases)

    @property
    def n_skipped(self) -> int:
        return sum(case.action == "skip" and case.success for case in self.cases)
