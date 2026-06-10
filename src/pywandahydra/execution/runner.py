"""Scenario runner — orchestrates sequential or parallel execution.

This module builds CasePlans from scenarios, dispatches them to workers
(sequentially or via multiprocessing), and aggregates results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence

from ..config.models import ModelSpecification, RunContext
from ..execution.artifacts import create_run_directories, write_run_log
from ..execution.case_plan import CasePlan, build_case_plans
from ..execution.journal import CaseJournal, resume_decision
from ..execution.worker import run_one_case
from ..scenarios.schema import ScenarioSpecification

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    """Serializable aggregated run result.

    Attributes:
        run_id: The unique run identifier.
        n_total: Total number of scenarios in the input.
        n_selected: Number of scenarios marked for inclusion.
        n_success: Number of cases that succeeded.
        n_failed: Number of cases that failed.
        n_skipped: Number of cases skipped (resume mode).
        results: Per-case result dictionaries.
    """

    run_id: str
    n_total: int
    n_selected: int
    n_success: int
    n_failed: int
    n_skipped: int = 0
    results: List[Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:  # noqa: D105
        if self.results is None:
            object.__setattr__(self, "results", [])


def run(
    *,
    model: ModelSpecification,
    ctx: RunContext,
    scenarios: Sequence[ScenarioSpecification],
    n_workers: int = 1,
    mode: Literal["sequential", "multiprocessing"] = "sequential",
    persist_manifest: bool = True,
    resume: bool = False,
    methodology: str = "default",
) -> RunResult:
    """Run scenarios with the specified model and context.

    This function performs orchestration only. The worker function handles
    per-case execution (model copy, parameter application, simulation,
    extraction, journaling).

    Args:
        model: The model specification for the run.
        ctx: The run context containing directory paths.
        scenarios: The list of scenario specifications to run.
        n_workers: Number of parallel workers (default 1 = sequential).
        mode: Execution mode used to select sequential vs multiprocessing.
        persist_manifest: Write run-level manifest/log file.
        resume: Skip already-completed cases with matching config hash.
        methodology: Post-processing methodology name.

    Returns:
        Aggregated RunResult.
    """
    run_root = Path(ctx.root_dir)

    # Create run directories and write log manifest
    create_run_directories(ctx)
    if persist_manifest:
        write_run_log(
            context_object=ctx,
            model_spec=model,
            scenarios=list(scenarios),
        )

    # Build case plans for included scenarios
    plans = build_case_plans(model, list(scenarios), run_root, methodology=methodology)
    if not plans:
        return RunResult(
            run_id=ctx.run_id,
            n_total=len(scenarios),
            n_selected=0,
            n_success=0,
            n_failed=0,
            n_skipped=0,
            results=[],
        )

    # Filter plans if resume mode is active
    plans_to_run = plans
    n_skipped = 0
    if resume:
        plans_to_run = []
        for plan in plans:
            journal = CaseJournal(plan.case_dir)
            decision = resume_decision(
                journal=journal,
                config_hash=plan.config_hash,
                readonly=plan.model_spec.readonly,
            )
            if decision == "skip":
                logger.info("Skipping completed case: %s", plan.case_id)
                n_skipped += 1
            elif decision == "rerun":
                logger.warning(
                    "Case %s will be re-run because of readonly=False.",
                    plan.case_id,
                )
                plans_to_run.append(plan)
            else:
                plans_to_run.append(plan)

    # Execute
    use_multiprocessing = mode == "multiprocessing" and n_workers > 1 and len(plans_to_run) > 1

    if not use_multiprocessing:
        results = [run_one_case(plan) for plan in plans_to_run]
    else:
        results = _run_multiprocess(plans=plans_to_run, n_workers=n_workers)

    # Aggregate results
    n_success = sum(1 for r in results if r.get("success") is True)
    n_failed = sum(1 for r in results if r.get("success") is False)

    # --- Aggregate per-case tables into a run-level summary ---
    if n_success > 0:
        from ..postprocessing.pdf_merge import merge_case_figure_pdfs
        from ..postprocessing.plots.renderer import aggregate_tables

        scenarios_dir = run_root / "scenarios"
        tables_dir = run_root / "tables"
        merged_pdf = run_root / "figures" / f"{ctx.run_id}_merged.pdf"

        aggregate_tables(scenarios_dir, tables_dir, run_id=ctx.run_id)
        merge_case_figure_pdfs(scenarios_dir, merged_pdf)

    return RunResult(
        run_id=ctx.run_id,
        n_total=len(scenarios),
        n_selected=len(plans),
        n_success=n_success,
        n_failed=n_failed,
        n_skipped=n_skipped,
        results=results,
    )


def _run_multiprocess(
    *,
    plans: List[CasePlan],
    n_workers: int,
) -> List[Dict[str, Any]]:
    """Run case plans in parallel using multiprocessing (spawn context).

    Args:
        plans: List of CasePlan objects to execute.
        n_workers: Number of parallel worker processes.

    Returns:
        List of per-case result dictionaries, sorted by case_id.
    """
    mp = get_context("spawn")
    with mp.Pool(processes=n_workers) as pool:
        results = pool.map(run_one_case, plans)

    # Sort by case_id for deterministic output ordering
    results.sort(key=lambda r: r.get("case_id", ""))
    return results
