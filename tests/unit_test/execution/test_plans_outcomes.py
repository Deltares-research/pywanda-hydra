from __future__ import annotations

import pickle
from pathlib import Path

from pywandahydra.execution.outcomes import CaseResult, RunResult
from pywandahydra.execution.plans import CasePlan, ModelSpecification
from pywandahydra.scenarios import ScenarioSpecification


def test_case_plan_round_trips_through_pickle(tmp_path: Path) -> None:
    model_path = tmp_path / "model.wdi"
    model_path.write_bytes(b"model")
    plan = CasePlan(
        case_id="case_one",
        case_dir=tmp_path / "case_one",
        model_spec=ModelSpecification(
            model_path=model_path,
            wanda_bin=tmp_path,
        ),
        scenario=ScenarioSpecification(number=1, include=True, name="case_one"),
    )

    assert pickle.loads(pickle.dumps(plan)) == plan


def test_run_result_counts_are_derived_and_pickle_safe() -> None:
    result = RunResult(
        run_id="run_one",
        cases=(
            CaseResult(case_id="one", action="simulate", success=True),
            CaseResult(case_id="two", action="postprocess", success=False, error="failed"),
            CaseResult(case_id="three", action="skip", success=True),
        ),
    )

    assert (result.n_success, result.n_failed, result.n_skipped) == (1, 1, 1)
    assert pickle.loads(pickle.dumps(result)) == result
