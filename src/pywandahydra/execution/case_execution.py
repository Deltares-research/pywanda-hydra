"""Simulation and WANDA-free post-processing for one prepared case."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Literal

from ..postprocessing.pipeline import PostProcessingOutcome, process_case_results
from ..results import ParquetResultStore
from ..wanda.model_access import WandaModelAccess
from .fingerprints import output_fingerprint, simulation_fingerprint
from .locking import CaseLock, CaseLockedError, case_log_handler
from .outcomes import CaseResult
from .plans import CasePlan
from .result_extraction import extract_simulation_data, requirements_from_scenario
from .run_directory import case_data_directory
from .status import CaseStatus, CaseStatusStore, SerializedPostProcessingOutcome

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def simulation_identity(plan: CasePlan) -> str:
    """Return the fingerprint governing stable simulation data."""
    return simulation_fingerprint(
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


def output_identity(plan: CasePlan) -> str:
    """Return the fingerprint governing derived case outputs."""
    return output_fingerprint(
        post_processing=plan.scenario.post_processing.model_dump(mode="json"),
        theme=None,
        table_formats=(),
        figure_formats=("pdf",),
    )


def _model_access() -> WandaModelAccess:
    """Import pywanda-backed access only in a simulation worker."""
    from ..wanda.pywanda_model_access import PywandaModelAccess

    return PywandaModelAccess()


def _run_simulations(access: object, model: object, plan: CasePlan) -> None:
    if plan.model_spec.run_steady:
        access.run_steady(model)  # type: ignore[attr-defined]
    if plan.model_spec.run_unsteady and access.simulation_time(model) > 0:  # type: ignore[attr-defined]
        access.run_unsteady(model)  # type: ignore[attr-defined]


def simulate_case(plan: CasePlan) -> CaseResult:
    """Create a fresh model copy and commit stable extracted results for one case."""
    started = time.perf_counter()
    simulation = simulation_identity(plan)
    output = output_identity(plan)
    store_status = CaseStatusStore(plan.case_dir)
    try:
        with CaseLock(plan.case_dir), case_log_handler(plan.case_dir):
            store_status.write(
                CaseStatus(
                    case_id=plan.case_id,
                    simulation_status="running",
                    postprocessing_status="pending",
                    simulation_fingerprint=simulation,
                    output_fingerprint=output,
                    started_at=_now_iso(),
                )
            )
            access = _model_access()
            model_path = access.prepare_scenario_model(
                plan.model_spec.model_path,
                plan.case_dir,
                plan.scenario.name,
            )
            with access.session(plan.model_spec, model_path) as model:
                for change in plan.scenario.parameter_changes:
                    access.apply(model, change)
                access.save_input(model)
                _run_simulations(access, model, plan)
                extracted = extract_simulation_data(
                    model,
                    access,
                    requirements_from_scenario(plan.scenario),
                )
            ParquetResultStore(case_data_directory(plan.case_dir)).write(
                extracted, fingerprint=simulation
            )
            duration = round(time.perf_counter() - started, 2)
            store_status.write(
                CaseStatus(
                    case_id=plan.case_id,
                    simulation_status="succeeded",
                    postprocessing_status="pending",
                    simulation_fingerprint=simulation,
                    output_fingerprint=output,
                    started_at=_now_iso(),
                    finished_at=_now_iso(),
                    duration_s=duration,
                )
            )
            return CaseResult(plan.case_id, "simulate", True, duration_s=duration)
    except CaseLockedError as exc:
        return CaseResult(plan.case_id, "simulate", False, error=str(exc))
    except Exception as exc:
        duration = round(time.perf_counter() - started, 2)
        error = f"{type(exc).__name__}: {exc}"
        store_status.write(
            CaseStatus(
                case_id=plan.case_id,
                simulation_status="failed",
                postprocessing_status="failed",
                simulation_fingerprint=simulation,
                output_fingerprint=output,
                started_at=_now_iso(),
                finished_at=_now_iso(),
                duration_s=duration,
                error_summary=error,
            )
        )
        logger.exception("Case %s simulation failed", plan.case_id)
        return CaseResult(plan.case_id, "simulate", False, duration_s=duration, error=error)


def postprocess_case(
    plan: CasePlan,
    *,
    action: Literal["simulate", "postprocess"] = "postprocess",
    simulation_duration_s: float | None = None,
) -> CaseResult:
    """Process committed case data under its lock without opening WANDA."""
    started = time.perf_counter()
    status_store = CaseStatusStore(plan.case_dir)
    output = output_identity(plan)
    try:
        with CaseLock(plan.case_dir), case_log_handler(plan.case_dir):
            current = status_store.read()
            simulation = (
                current.simulation_fingerprint
                if current and current.simulation_fingerprint
                else simulation_identity(plan)
            )
            status_store.write(
                CaseStatus(
                    case_id=plan.case_id,
                    simulation_status="succeeded",
                    postprocessing_status="running",
                    simulation_fingerprint=simulation,
                    output_fingerprint=output,
                    started_at=current.started_at if current else _now_iso(),
                )
            )
            outcomes = process_case_results(
                store=ParquetResultStore(case_data_directory(plan.case_dir)),
                scenario=plan.scenario,
                case_dir=plan.case_dir,
                analysis_metadata=plan.analysis_metadata,
            )
            serialized = _serialize_outcomes(outcomes, plan)
            failed = any(outcome.status == "failed" for outcome in outcomes)
            duration = round((simulation_duration_s or 0) + time.perf_counter() - started, 2)
            status_store.write(
                CaseStatus(
                    case_id=plan.case_id,
                    simulation_status="succeeded",
                    postprocessing_status="failed" if failed else "succeeded",
                    simulation_fingerprint=simulation,
                    output_fingerprint=output,
                    started_at=current.started_at if current else _now_iso(),
                    finished_at=_now_iso(),
                    duration_s=duration,
                    postprocessing_outcomes=serialized,
                    generated_paths=tuple(
                        path for outcome in serialized for path in outcome.created_paths
                    ),
                )
            )
            return CaseResult(plan.case_id, action, not failed, duration, post_processing=outcomes)
    except CaseLockedError as exc:
        return CaseResult(plan.case_id, action, False, error=str(exc))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("Case %s post-processing failed", plan.case_id)
        return CaseResult(plan.case_id, action, False, error=error)


def _serialize_outcomes(
    outcomes: tuple[PostProcessingOutcome, ...], plan: CasePlan
) -> tuple[SerializedPostProcessingOutcome, ...]:
    return tuple(
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
