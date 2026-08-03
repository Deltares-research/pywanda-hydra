"""Execution package - runner, worker, journal, case planning."""

from typing import Any

from .case_plan import CasePlan, build_case_plans
from .journal import CaseJournal, CaseState

__all__ = ["CaseJournal", "CasePlan", "CaseState", "RunResult", "build_case_plans", "run"]


def __getattr__(name: str) -> Any:
	"""Load the legacy runner only when a caller explicitly requests it."""
	if name in {"RunResult", "run"}:
		from .runner import RunResult, run

		return {"RunResult": RunResult, "run": run}[name]
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
