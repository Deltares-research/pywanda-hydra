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
from importlib import import_module
from typing import Any, cast

from filelock import Timeout

from ..execution.case_plan import CasePlan
from ..execution.journal import CaseJournal, _now_iso, resume_decision
from ..postprocessing.core.context import CaseContext, ExtractionContext
from ..postprocessing.core.pipeline import run_postprocessing
from ..postprocessing.extraction.extract import extract_all
from ..postprocessing.extraction.extractors import bootstrap as bootstrap_extractors
from ..postprocessing.extraction.extractors import resolve_extractor
from ..postprocessing.io.cache import ParquetCache
from ..postprocessing.plotting.theme_registry import get_theme
from ..postprocessing.workflows import bootstrap as bootstrap_workflows
from ..wanda.adapter import WandaAdapter

logger = logging.getLogger(__name__)


def _load_adapter(plan: CasePlan) -> WandaAdapter:
    """Instantiate the configured adapter class for this case.

    Implemented to support loading of custom adapter (e.g., FakeAdapter for testing)
    specified by import path in the CasePlan.
    """
    module_name, _, class_name = plan.adapter_class.partition(":")
    if not module_name or not class_name:
        raise ValueError(
            f"Invalid adapter class path '{plan.adapter_class}'. "
            "Expected format 'package.module:ClassName'."
        )

    module = import_module(module_name)
    adapter_class = getattr(module, class_name)
    return cast(WandaAdapter, adapter_class())


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

    # Ensure built-in workflows are registered in this process (idempotent,
    # required under multiprocessing 'spawn' where module-level side effects
    # do not propagate from the parent process).
    bootstrap_workflows()
    bootstrap_extractors()

    # Hold the case lock for the entire execution so two processes can never
    # work the same case directory concurrently — a second WANDA session on
    # the same model files blocks indefinitely inside pywanda.WandaModel.
    # FileLock is reentrant, so nested `with journal:` transitions still work.
    try:
        # Only continue if we can acquire the lock.
        journal.acquire()
    except Timeout:
        error_msg = (
            "Case directory is locked by another process — a previous or "
            "concurrent run may still be active on this case."
        )
        logger.error("Case %s: %s", plan.case_id, error_msg)
        return {
            "case_id": plan.case_id,
            "success": False,
            "error": error_msg,
            "scenario_dir": str(plan.case_dir),
        }
    try:
        return _execute_case(plan, journal)
    finally:
        journal.release()


def _execute_case(plan: CasePlan, journal: CaseJournal) -> dict[str, Any]:
    """Execute the case body. The caller must hold the case lock."""
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
    logger.info("Case %s: Loading adapter...", plan.case_id)
    adapter = _load_adapter(plan)
    logger.info("Case %s: Adapter loaded successfully", plan.case_id)

    try:
        # --- Prepare scenario model copy ---
        logger.info(
            "Case %s: Preparing scenario model from %s",
            plan.case_id,
            plan.model_spec.model_path,
        )
        scenario_model_path = adapter.prepare_scenario_model(
            plan.model_spec.model_path,
            plan.case_dir,
            plan.scenario.meta.name,
            readonly=plan.model_spec.readonly,
        )
        logger.info("Case %s: Model prepared at %s", plan.case_id, scenario_model_path)
        journal.event("model_prepared", path=scenario_model_path)

        # --- Open WANDA session (single open per case) ---
        logger.info("Case %s: Opening WANDA session...", plan.case_id)
        logger.info(
            "Case %s: This may take several seconds while WANDA initializes",
            plan.case_id,
        )
        with adapter.session(plan.model_spec, scenario_model_path) as model:
            logger.info("Case %s: WANDA session opened successfully", plan.case_id)
            # Apply global overrides
            logger.info(
                "Case %s: Applying %d global overrides",
                plan.case_id,
                len(plan.model_spec.global_overrides),
            )
            for change in plan.model_spec.global_overrides:
                adapter.apply(model, change)

            # Apply scenario-specific parameter changes
            logger.info(
                "Case %s: Applying %d scenario parameters",
                plan.case_id,
                len(plan.scenario.parameters),
            )
            for change in plan.scenario.parameters:
                adapter.apply(model, change)

            journal.event(
                "params_applied",
                global_count=len(plan.model_spec.global_overrides),
                scenario_count=len(plan.scenario.parameters),
            )

            # Save and run
            logger.info("Case %s: Saving model input", plan.case_id)
            adapter.save_input(model)

            if plan.model_spec.run_steady:
                logger.info(
                    "Case %s: Starting steady-state simulation...", plan.case_id
                )
                adapter.run_steady(model)
                logger.info("Case %s: Steady-state simulation completed", plan.case_id)
                journal.event("steady_done")

            if plan.model_spec.run_unsteady:
                logger.info("Case %s: Checking simulation time", plan.case_id)
                sim_time = adapter.simulation_time(model)
                logger.info("Case %s: Simulation time = %s", plan.case_id, sim_time)
                if sim_time > 0:
                    logger.info(
                        "Case %s: Starting unsteady simulation...", plan.case_id
                    )
                    adapter.run_unsteady(model)
                    logger.info("Case %s: Unsteady simulation completed", plan.case_id)
                    journal.event("unsteady_done")

            # --- Extract results while model is open (single pass) ---
            logger.info("Case %s: Extracting results...", plan.case_id)
            extracted = extract_all(model, plan.scenario, adapter)
            logger.info("Case %s: Extraction completed", plan.case_id)
            journal.event(
                "extracted",
                has_components=not extracted["components"].empty,
                n_routes=len(extracted["routes"]),
            )

            # --- Run custom extractors while model is open ---
            custom_extracted: dict[str, Any] = {}
            cache = ParquetCache(plan.case_dir)
            logger.info(
                "Case %s: Running %d custom extractors",
                plan.case_id,
                len(plan.extractors),
            )
            for extractor_spec in plan.extractors:
                extractor_name = extractor_spec.get("name")
                extractor_params = extractor_spec.get("params", {})
                if not extractor_name:
                    logger.warning(
                        "Skipping extractor spec with no name: %s", extractor_spec
                    )
                    continue

                try:
                    extractor = resolve_extractor(extractor_name, extractor_params)
                    extraction_ctx = ExtractionContext(
                        model=model,
                        adapter=adapter,
                        scenario=plan.scenario,
                        case_id=plan.case_id,
                        case_dir=plan.case_dir,
                        cache=cache,
                    )
                    result = extractor.extract(extraction_ctx)
                    if result:
                        custom_extracted[extractor_name] = result
                        logger.info(
                            "Extractor '%s' completed for case '%s'.",
                            extractor_name,
                            plan.case_id,
                        )
                    else:
                        logger.debug(
                            "Extractor '%s' returned no data for case '%s'.",
                            extractor_name,
                            plan.case_id,
                        )
                except Exception as e:
                    logger.error(
                        "Extractor '%s' failed for case '%s': %s",
                        extractor_name,
                        plan.case_id,
                        e,
                        exc_info=True,
                    )

        # --- Cache extracted data (standard + custom) to Parquet ---
        logger.info("Case %s: WANDA session closed, writing cache...", plan.case_id)
        cache = ParquetCache(plan.case_dir)
        artefacts = cache.write(extracted)
        custom_artefacts = cache.write_custom(custom_extracted)
        artefacts.update(custom_artefacts)
        logger.info(
            "Case %s: Cache written with %d artefacts", plan.case_id, len(artefacts)
        )
        journal.event("cached", artefacts=artefacts)

        # --- Post-processing: run workflow-driven steps ---
        logger.info(
            "Case %s: Starting post-processing (%s)...",
            plan.case_id,
            plan.workflow_name,
        )
        theme = get_theme(plan.scenario.post_processing.theme)
        postprocessing_ctx = CaseContext(
            cache=cache,
            scenario=plan.scenario,
            case_dir=plan.case_dir,
            theme=theme,
        )
        with journal:
            journal.transition("RUNNING", postprocess_status="RUNNING")
        postprocessing_results = run_postprocessing(
            postprocessing_ctx,
            workflow_name=plan.workflow_name,
            workflow_params=plan.workflow_params,
        )
        logger.info(
            "Case %s: Post-processing completed with results: %s",
            plan.case_id,
            postprocessing_results,
        )

        postprocessing_success = all(postprocessing_results.values())
        postprocessing_status = "DONE" if postprocessing_success else "FAILED"

        journal.event(
            "postprocessed",
            steps={name: ok for name, ok in postprocessing_results.items()},
        )

        # --- Transition: SUCCEEDED ---
        duration = time.perf_counter() - start_time
        with journal:
            journal.transition(
                "SUCCEEDED",
                finished_at=_now_iso(),
                duration_s=round(duration, 2),
                postprocess_status=postprocessing_status,
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
                postprocess_status="FAILED",
                error=error_msg,
            )
        logger.error("Case %s failed: %s", plan.case_id, error_msg)
        return {
            "case_id": plan.case_id,
            "success": False,
            "postprocess_status": "FAILED",
            "error": error_msg,
            "duration_s": round(duration, 2),
            "scenario_dir": str(plan.case_dir),
        }
