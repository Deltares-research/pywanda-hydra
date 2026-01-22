from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import get_context
from typing import Any, Dict, List, Optional, Sequence

from ..config.models import ModelSpecification, RunContext
from ..execution.artifacts import create_run_directories, write_run_log
from ..execution.worker import run_one_scenario
from ..scenarios.schema import ScenarioSpecification


@dataclass(frozen=True)
class RunResult:
    """Serializable aggregated run result."""

    run_id: str
    n_total: int
    n_selected: int
    n_success: int
    n_failed: int
    results: List[Dict[str, Any]]


def run(
    *,
    model: ModelSpecification,
    ctx: RunContext,
    scenarios: Sequence[ScenarioSpecification],
    n_workers: int = 1,
    persist_manifest: bool = True,
) -> RunResult:
    """Run scenarios with the specified model and context.

    Notes
    -----
    - This function performs orchestration only.
    - The worker function is responsible for:
        * creating per-scenario directories
        * copying the base model into scenario directory
        * opening the copied model
        * applying overrides/parameters and running WANDA

    Parameters
    ----------
    model : ModelSpecification
        The model specification to use for the run.
    ctx : RunContext
        The run context containing directory paths.
    scenarios : Sequence[ScenarioSpecification]
        The list of scenario specifications to run.
    n_workers : int, optional
        Number of parallel workers to use (default is 1, meaning no parallelism).
    persist_manifest : bool, optional
        Store run manifest/log file (default is True) of scenario, model, and context details.
    """
    # Create run directories and write log manifest
    create_run_directories(ctx)
    if persist_manifest:
        write_run_log(
            context_object=ctx,
            model_spec=model,
            scenarios=list(scenarios),
        )

    # Only run scenarios marked as included
    selected = [s for s in scenarios if s.meta.include]
    if not selected:
        return RunResult(
            run_id=ctx.run_id,
            n_total=len(scenarios),
            n_selected=0,
            n_success=0,
            n_failed=0,
            results=[],
        )

    # Execute scenarios
    if n_workers <= 1:
        results = [
            run_one_scenario(model_specifications=model, scenario=s, ctx=ctx) for s in selected
        ]
    else:
        results = _run_multiprocess(model=model, ctx=ctx, scenarios=selected, n_workers=n_workers)

    # Aggregate results
    n_success = sum(1 for r in results if r.get("success") is True)
    n_failed = len(results) - n_success

    return RunResult(
        run_id=ctx.run_id,
        n_total=len(scenarios),
        n_selected=len(selected),
        n_success=n_success,
        n_failed=n_failed,
        results=results,
    )


def _run_multiprocess(
    *,
    model: ModelSpecification,
    ctx: RunContext,
    scenarios: List[ScenarioSpecification],
    n_workers: int,
) -> List[Dict[str, Any]]:
    """Run scenarios in parallel using multiprocessing.

    Parameters
    ----------
    model : ModelSpecification
        The model specification to use for the run.
    ctx : RunContext
        The run context containing directory paths.
    scenarios : List[ScenarioSpecification]
        The list of scenario specifications to run.
    n_workers : int
        Number of parallel workers to use.

    Returns
    -------
    List[Dict[str, Any]]
        List of results from each scenario execution.
    """
    # Spawn a new Python process for each worker
    mp = get_context("spawn")

    # Create argument tuples
    jobs = [(model, s, ctx) for s in scenarios]

    with mp.Pool(processes=n_workers) as pool:
        # starmap calls run_one_scenario(model, scenario, ctx)
        results = pool.starmap(run_one_scenario, jobs)

    return results
