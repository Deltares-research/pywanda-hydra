"""Worker module - executes one case under a defensive local lock."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from ..execution.case_plan import CasePlan
from ..postprocessing.pipeline import process_case_results
from ..results import ParquetResultStore
from ..wanda.model_access import WandaModelAccess
from ..wanda.pywanda_model_access import PywandaModelAccess
from .fingerprints import output_fingerprint, simulation_fingerprint
from .locking import CaseLock, CaseLockedError, case_log_handler
from .result_extraction import extract_simulation_data, requirements_from_scenario
from .run_directory import case_data_directory, recovery_decision
from .status import CaseStatus, CaseStatusStore, SerializedPostProcessingOutcome

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current UTC time in the persisted status format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class CaseResult(TypedDict, total=False):
    """Result of executing a single case, returned by ``run_one_case``.

    All fields are optional since the skip/success/failure branches each
    populate a different subset.
    """

    case_id: str
    success: bool
    skipped: bool
    error: str
    duration_s: float
    postprocess_status: str
    scenario_dir: str


def _build_model_access() -> WandaModelAccess:
    """Construct the internal production model-access implementation."""
    return PywandaModelAccess()


def run_one_case(plan: CasePlan) -> CaseResult:
    """Execute a single case according to its CasePlan.

    This is the atomic unit of work dispatched by the runner - either
    sequentially or via multiprocessing.

    Args:
        plan: Immutable case plan containing all execution parameters.

    Returns:
        Dict with keys: case_id, success, error (if failed), scenario_dir.
    """
    try:
        with CaseLock(plan.case_dir):
            with case_log_handler(plan.case_dir):
                return _execute_case(plan)
    except CaseLockedError as exc:
        logger.error("Case %s: %s", plan.case_id, exc)
        return {
            "case_id": plan.case_id,
            "success": False,
            "error": str(exc),
            "scenario_dir": str(plan.case_dir),
        }


def _apply_parameters(
    adapter: WandaModelAccess,
    model: Any,
    plan: CasePlan,
) -> None:
    """Apply scenario-specific parameter changes."""
    logger.info(
        "Case %s: Applying %d scenario parameters",
        plan.case_id,
        len(plan.scenario.parameter_changes),
    )
    for change in plan.scenario.parameter_changes:
        adapter.apply(model, change)



def _run_simulations(
    adapter: WandaModelAccess,
    model: Any,
    plan: CasePlan,
) -> None:
    """Run steady and/or unsteady simulations as configured by the model spec."""
    if plan.model_spec.run_steady:
        logger.info("Case %s: Starting steady-state simulation...", plan.case_id)
        adapter.run_steady(model)
        logger.info("Case %s: Steady-state simulation completed", plan.case_id)

    if plan.model_spec.run_unsteady:
        logger.info("Case %s: Checking simulation time", plan.case_id)
        sim_time = adapter.simulation_time(model)
        logger.info("Case %s: Simulation time = %s", plan.case_id, sim_time)
        if sim_time > 0:
            logger.info("Case %s: Starting unsteady simulation...", plan.case_id)
            adapter.run_unsteady(model)
            logger.info("Case %s: Unsteady simulation completed", plan.case_id)


def _finalize_success(
    plan: CasePlan,
    status_store: CaseStatusStore,
    status: CaseStatus,
    start_time: float,
    outcomes: tuple[SerializedPostProcessingOutcome, ...],
) -> CaseResult:
    """Persist a successful simulation and current post-processing result."""
    duration = time.perf_counter() - start_time
    postprocessing_status: Literal["succeeded", "failed"] = "succeeded" if all(
        outcome.status != "failed" for outcome in outcomes
    ) else "failed"
    status_store.write(
        CaseStatus(
            case_id=plan.case_id,
            simulation_status="succeeded",
            postprocessing_status=postprocessing_status,
            simulation_fingerprint=status.simulation_fingerprint,
            output_fingerprint=status.output_fingerprint,
            started_at=status.started_at,
            finished_at=_now_iso(),
            duration_s=round(duration, 2),
            postprocessing_outcomes=outcomes,
            generated_paths=tuple(path for outcome in outcomes for path in outcome.created_paths),
        )
    )

    logger.info("Case %s succeeded in %.1fs", plan.case_id, duration)
    return {
        "case_id": plan.case_id,
        "success": True,
        "duration_s": round(duration, 2),
        "scenario_dir": str(plan.case_dir),
    }


def _finalize_failure(
    plan: CasePlan,
    status_store: CaseStatusStore,
    status: CaseStatus,
    start_time: float,
    exc: Exception,
) -> CaseResult:
    """Persist the latest error without treating lock contention as a failure."""
    duration = time.perf_counter() - start_time
    error_msg = f"{type(exc).__name__}: {exc}"
    status_store.write(
        CaseStatus(
            case_id=plan.case_id,
            simulation_status="failed",
            postprocessing_status="failed",
            simulation_fingerprint=status.simulation_fingerprint,
            output_fingerprint=status.output_fingerprint,
            started_at=status.started_at,
            finished_at=_now_iso(),
            duration_s=round(duration, 2),
            error_summary=error_msg,
        )
    )
    logger.error("Case %s failed: %s", plan.case_id, error_msg, exc_info=True)
    return {
        "case_id": plan.case_id,
        "success": False,
        "postprocess_status": "FAILED",
        "error": error_msg,
        "duration_s": round(duration, 2),
        "scenario_dir": str(plan.case_dir),
    }


def _execute_case(plan: CasePlan) -> CaseResult:
    """Execute the case body while the caller holds its case lock."""
    status_store = CaseStatusStore(plan.case_dir)
    status = status_store.read()
    simulation = simulation_fingerprint(
        model_path=plan.model_spec.model_path,
        upgrade=plan.model_spec.upgrade,
        wanda_version=None,
        pywanda_version=None,
        run_steady=plan.model_spec.run_steady,
        run_unsteady=plan.model_spec.run_unsteady,
        parameter_changes=[
            change.model_dump(mode="json") for change in plan.scenario.parameter_changes
        ],
    )
    output = output_fingerprint(
        post_processing=plan.scenario.post_processing.model_dump(mode="json"),
        theme=None,
        table_formats=(),
        figure_formats=("pdf",),
    )
    store = ParquetResultStore(case_data_directory(plan.case_dir))
    inventory = store.inventory()
    outputs_current = status is not None and all(
        (plan.case_dir / path).is_file() for path in status.generated_paths
    )
    decision = recovery_decision(
        status=status,
        simulation_fingerprint=simulation,
        output_fingerprint=output,
        result_store_complete=store.is_complete(),
        inventory=inventory,
        requirements=requirements_from_scenario(plan.scenario),
        outputs_current=outputs_current,
    )
    if decision == "skip":
        logger.info("Case %s already completed - skipping.", plan.case_id)
        return {
            "case_id": plan.case_id,
            "success": True,
            "skipped": True,
            "scenario_dir": str(plan.case_dir),
        }

    start_time = time.perf_counter()
    current_status = CaseStatus(
        case_id=plan.case_id,
        simulation_status="running" if decision == "simulate" else "succeeded",
        postprocessing_status="running" if decision == "postprocess" else "pending",
        simulation_fingerprint=simulation,
        output_fingerprint=output,
        started_at=_now_iso(),
    )
    status_store.write(current_status)
    if decision == "postprocess":
        return _postprocess(plan, store, status_store, current_status, start_time)
    logger.info("Case %s: Building model access...", plan.case_id)
    adapter = _build_model_access()
    logger.info("Case %s: Model access ready", plan.case_id)

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
            plan.scenario.name,
            reuse_existing_data=plan.model_spec.reuse_existing_data,
        )
        logger.info("Case %s: Model prepared at %s", plan.case_id, scenario_model_path)

        # --- Open WANDA session (single open per case) ---
        logger.info("Case %s: Opening WANDA session...", plan.case_id)
        logger.info(
            "Case %s: This may take several seconds while WANDA initializes",
            plan.case_id,
        )
        with adapter.session(plan.model_spec, scenario_model_path) as model:
            logger.info("Case %s: WANDA session opened successfully", plan.case_id)

            _apply_parameters(adapter, model, plan)

            # Save and run
            logger.info("Case %s: Saving model input", plan.case_id)
            adapter.save_input(model)

            _run_simulations(adapter, model, plan)

            # --- Extract results while model is open (single pass) ---
            logger.info("Case %s: Extracting results...", plan.case_id)
            extracted = extract_simulation_data(
                model,
                adapter,
                requirements_from_scenario(plan.scenario),
            )
            logger.info("Case %s: Extraction completed", plan.case_id)

        # --- Persist extracted data to Parquet ---
        logger.info("Case %s: WANDA session closed, writing results...", plan.case_id)
        store = ParquetResultStore(case_data_directory(plan.case_dir))
        store.write(extracted, fingerprint=simulation)
        logger.info("Case %s: Results written", plan.case_id)
        return _postprocess(plan, store, status_store, current_status, start_time)

    except Exception as e:
        return _finalize_failure(plan, status_store, current_status, start_time, e)


def _postprocess(
    plan: CasePlan,
    store: ParquetResultStore,
    status_store: CaseStatusStore,
    status: CaseStatus,
    start_time: float,
) -> CaseResult:
    try:
        outcomes = process_case_results(
            store=store,
            scenario=plan.scenario,
            case_dir=plan.case_dir,
            analysis_metadata=plan.analysis_metadata,
        )
        serialized = tuple(
            SerializedPostProcessingOutcome(
                routine_name=outcome.routine_name,
                status=outcome.status,
                skip_reason=outcome.skip_reason,
                error=outcome.error,
                created_paths=tuple(
                    str(path.relative_to(plan.case_dir)) for path in outcome.created_paths
                ),
            )
            for outcome in outcomes
        )
        return _finalize_success(plan, status_store, status, start_time, serialized)
    except Exception as exc:
        return _finalize_failure(plan, status_store, status, start_time, exc)
