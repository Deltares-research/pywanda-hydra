from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pywandahydra.execution.outcomes import CaseResult
from pywandahydra.execution.plans import CasePlan, ModelSpecification
from pywandahydra.execution.run_cases import run_cases
from pywandahydra.scenarios import ScenarioSpecification


def _plan(tmp_path: Path, case_id: str) -> CasePlan:
    model_path = tmp_path / "model.wdi"
    model_path.write_bytes(b"model")
    return CasePlan(
        case_id=case_id,
        case_dir=tmp_path / case_id,
        model_spec=ModelSpecification(
            model_path=model_path,
            wanda_bin=tmp_path,
        ),
        scenario=ScenarioSpecification(number=1, include=True, name=case_id),
    )


def test_mixed_actions_only_simulate_selected_cases(tmp_path: Path) -> None:
    plans = tuple(_plan(tmp_path, case_id) for case_id in ("simulate", "postprocess", "skip"))
    simulated = CaseResult("simulate", "simulate", True, duration_s=1.0)
    postprocessed = CaseResult("postprocess", "postprocess", True)
    simulated_postprocessed = CaseResult("simulate", "simulate", True)

    with (
        patch(
            "pywandahydra.execution.run_cases.select_action",
            side_effect=("simulate", "postprocess", "skip"),
        ),
        patch("pywandahydra.execution.run_cases.simulate_case", return_value=simulated) as simulate,
        patch(
            "pywandahydra.execution.run_cases.postprocess_case",
            side_effect=(simulated_postprocessed, postprocessed),
        ) as postprocess,
    ):
        results = run_cases(plans, workers=1)

    assert [result.action for result in results] == ["simulate", "postprocess", "skip"]
    assert simulate.call_args_list[0].args == (plans[0],)
    assert postprocess.call_args_list[0].kwargs["action"] == "simulate"
    assert postprocess.call_args_list[1].args == (plans[1],)


def test_multiple_simulations_use_spawn_dispatch(tmp_path: Path) -> None:
    plans = tuple(_plan(tmp_path, case_id) for case_id in ("one", "two"))

    with (
        patch(
            "pywandahydra.execution.run_cases.select_action",
            side_effect=("simulate", "simulate"),
        ),
        patch("pywandahydra.execution.run_cases.get_context") as get_context,
    ):
        pool = get_context.return_value.Pool.return_value.__enter__.return_value
        pool.map.return_value = [
            CaseResult("one", "simulate", False, error="failed"),
            CaseResult("two", "simulate", False, error="failed"),
        ]
        results = run_cases(plans, workers=2)

    get_context.assert_called_once_with("spawn")
    assert [result.success for result in results] == [False, False]
