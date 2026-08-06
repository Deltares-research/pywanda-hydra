"""Select case recovery actions and dispatch simulation work."""

from __future__ import annotations

from multiprocessing import get_context

from ..results import ParquetResultStore
from .case_execution import output_identity, postprocess_case, simulate_case, simulation_identity
from .outcomes import CaseResult
from .plans import CasePlan
from .result_extraction import requirements_from_scenario
from .run_directory import RecoveryAction, case_data_directory, recovery_decision
from .status import CaseStatusStore


def select_action(plan: CasePlan) -> RecoveryAction:
    """Choose a recovery action from durable files only."""
    status = CaseStatusStore(plan.case_dir).read()
    store = ParquetResultStore(case_data_directory(plan.case_dir))
    outputs_current = status is not None and all(
        (plan.case_dir / path).is_file() for path in status.generated_paths
    )
    return recovery_decision(
        status=status,
        simulation_fingerprint=simulation_identity(plan),
        output_fingerprint=output_identity(plan),
        result_store_complete=store.is_complete(),
        inventory=store.inventory(),
        requirements=requirements_from_scenario(plan.scenario),
        outputs_current=outputs_current,
    )


def run_cases(plans: tuple[CasePlan, ...], workers: int) -> tuple[CaseResult, ...]:
    """Execute selected actions, using spawned workers only for simulations."""
    actions = {plan.case_id: select_action(plan) for plan in plans}
    simulations = [plan for plan in plans if actions[plan.case_id] == "simulate"]
    if workers > 1 and len(simulations) > 1:
        with get_context("spawn").Pool(processes=workers) as pool:
            simulated = pool.map(simulate_case, simulations)
    else:
        simulated = [simulate_case(plan) for plan in simulations]
    simulation_results = {result.case_id: result for result in simulated}

    results: list[CaseResult] = []
    for plan in plans:
        action = actions[plan.case_id]
        if action == "skip":
            results.append(CaseResult(plan.case_id, "skip", True))
        elif action == "postprocess":
            results.append(postprocess_case(plan))
        else:
            simulated_result = simulation_results[plan.case_id]
            results.append(
                postprocess_case(
                    plan,
                    action="simulate",
                    simulation_duration_s=simulated_result.duration_s,
                )
                if simulated_result.success
                else simulated_result
            )
    return tuple(results)
