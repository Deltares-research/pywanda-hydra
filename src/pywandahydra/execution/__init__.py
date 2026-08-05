"""Execution package - plans, status, locking, runner, and worker."""

from typing import Any

from .case_plan import CasePlan, build_case_plans
from .status import CaseStatus, CaseStatusStore

__all__ = ["CasePlan", "CaseStatus", "CaseStatusStore", "RunResult", "build_case_plans", "run"]


def __getattr__(name: str) -> Any:
    """Load the legacy runner only when a caller explicitly requests it."""
    if name in {"RunResult", "run"}:
        from .runner import RunResult, run

        return {"RunResult": RunResult, "run": run}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
