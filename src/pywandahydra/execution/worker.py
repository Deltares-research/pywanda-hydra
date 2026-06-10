"""Worker module — executes a single scenario case.

Responsible for:
- Creating the per-case directory
- Copying the base model
- Opening the model via the adapter
- Applying global overrides and scenario parameters
- Running steady/unsteady simulations
- Extracting results and writing to Parquet cache
- Journaling status transitions (state.json + events.jsonl)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from ..execution.case_plan import CasePlan
from ..execution.journal import CaseJournal, _now_iso, resume_decision
from ..postprocessing.cache import ParquetCache
from ..postprocessing.extract import extract_all
from ..postprocessing.methodologies import bootstrap as bootstrap_methodologies
from ..postprocessing.pipeline import PostProcessingContext, run_postprocessing
from ..wanda.api import apply_parameter_change
from ..wanda.create_scenario import prepare_scenario_model
from ..wanda.session import wanda_session

logger = logging.getLogger(__name__)


def run_one_case(plan: CasePlan) -> dict[str, Any]:
    """Execute a single case according to its CasePlan.

    This is the atomic unit of work dispatched by the runner — either
    sequentially or via multiprocessing.

    Args:
        plan: Immutable case plan containing all execution parameters.

    Returns:
        Dict with keys: case_id, success, error (if failed), scenario_dir.
    """
    journal = CaseJournal(plan.case_dir)

    # Ensure built-in methodologies are registered in this process (idempotent,
    # required under multiprocessing 'spawn' where module-level side effects
    # do not propagate from the parent process).
    bootstrap_methodologies()

    # --- Check idempotency using shared resume policy ---
    decision = resume_decision(
        journal=journal,
        config_hash=plan.config_hash,
        readonly=plan.model_spec.readonly,
    )
    if decision == "skip":
        logger.info("Case %s already completed — skipping.", plan.case_id)
        return {
            "case_id": plan.case_id,
            "success": True,
            "skipped": True,
            "scenario_dir": str(plan.case_dir),
        }

    # --- Transition: RUNNING ---
    with journal:
        journal.transition(
            "RUNNING",
            started_at=_now_iso(),
            worker_pid=os.getpid(),
            attempt=plan.attempt,
            config_hash=plan.config_hash,
        )

    start_time = time.perf_counter()

    try:
        # --- Prepare scenario model copy ---
        scenario_model_path = prepare_scenario_model(
            base_model_path=str(plan.model_spec.model_path),
            scenario_dir=plan.case_dir,
            scenario_name=plan.scenario.meta.name,
            readonly=plan.model_spec.readonly,
        )
        journal.event("model_prepared", path=scenario_model_path)

        # --- Open WANDA session (single open per case) ---
        with wanda_session(plan.model_spec, model_path=scenario_model_path) as model:
            # Apply global overrides
            for change in plan.model_spec.global_overrides:
                apply_parameter_change(model, change)

            # Apply scenario-specific parameter changes
            for change in plan.scenario.parameters:
                apply_parameter_change(model, change)

            journal.event(
                "params_applied",
                global_count=len(plan.model_spec.global_overrides),
                scenario_count=len(plan.scenario.parameters),
            )

            # Save and run
            model.save_model_input()

            if plan.model_spec.run_steady:
                model.run_steady()
                journal.event("steady_done")

            if plan.model_spec.run_unsteady:
                sim_time = model.get_property("Simulation time").get_scalar_float()
                if sim_time > 0:
                    model.run_unsteady()
                    journal.event("unsteady_done")

            # --- Extract results while model is open (single pass) ---
            extracted = extract_all(model, plan.scenario)
            journal.event(
                "extracted",
                has_components=not extracted["components"].empty,
                n_routes=len(extracted["routes"]),
            )

        # --- Cache extracted data to Parquet ---
        cache = ParquetCache(plan.case_dir)
        artefacts = cache.write(extracted)
        journal.event("cached", artefacts=artefacts)

        # --- Post-processing: run methodology-driven steps ---
        pp_ctx = PostProcessingContext(
            cache=cache,
            scenario=plan.scenario,
            case_dir=plan.case_dir,
        )
        with journal:
            journal.transition("RUNNING", postprocess_status="RUNNING")
        pp_results = run_postprocessing(pp_ctx, methodology=plan.methodology)

        pp_success = all(pp_results.values())
        pp_status = "DONE" if pp_success else "FAILED"

        journal.event(
            "postprocessed",
            steps={name: ok for name, ok in pp_results.items()},
        )

        # --- Transition: SUCCEEDED ---
        duration = time.perf_counter() - start_time
        with journal:
            journal.transition(
                "SUCCEEDED",
                finished_at=_now_iso(),
                duration_s=round(duration, 2),
                postprocess_status=pp_status,
                artefacts=artefacts,
            )

        logger.info("Case %s succeeded in %.1fs", plan.case_id, duration)
        return {
            "case_id": plan.case_id,
            "success": True,
            "duration_s": round(duration, 2),
            "scenario_dir": str(plan.case_dir),
        }

    except Exception as e:
        # --- Transition: FAILED ---
        duration = time.perf_counter() - start_time
        error_msg = f"{type(e).__name__}: {e}"
        with journal:
            journal.transition(
                "FAILED",
                finished_at=_now_iso(),
                duration_s=round(duration, 2),
                error=error_msg,
            )
        logger.error("Case %s failed: %s", plan.case_id, error_msg)
        return {
            "case_id": plan.case_id,
            "success": False,
            "error": error_msg,
            "duration_s": round(duration, 2),
            "scenario_dir": str(plan.case_dir),
        }
