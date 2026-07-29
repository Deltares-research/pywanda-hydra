from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from filelock import FileLock

from pywandahydra.config.models import ModelSpecification
from pywandahydra.execution.case_plan import CasePlan
from pywandahydra.execution.journal import CaseJournal
from pywandahydra.execution.worker import run_one_case
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


class TestWorkerFailurePath(unittest.TestCase):
    def test_run_one_case_reports_failure_and_journals_failed_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            model_path = root_dir / "base_model.wdi"
            model_path.write_bytes(b"base_model")

            model_spec = ModelSpecification(
                model_path=model_path,
                wanda_bin=Path(r"c:\wanda\bin"),
                base_model_name="base_model",
                reuse_existing_data=False,
                run_steady=True,
                run_unsteady=False,
            )
            scenario = ScenarioSpecification(
                meta=ScenarioMeta.model_validate(
                    {
                        "Number": 1,
                        "Include": True,
                        "Name": "case_failing",
                    }
                )
            )
            plan = CasePlan(
                case_id="case_failing",
                case_dir=root_dir / "scenarios" / "case_failing",
                model_spec=model_spec,
                scenario=scenario,
                adapter_class="unit_test.wanda.fakes:FailingWandaAdapter",
            )

            with patch(
                "pywandahydra.execution.worker.bootstrap_workflows",
                return_value=None,
            ):
                result = run_one_case(plan)

            self.assertFalse(result["success"])
            self.assertEqual(result["case_id"], "case_failing")
            self.assertEqual(result["postprocess_status"], "FAILED")
            self.assertIn("simulated steady-state failure", result["error"])

            journal = CaseJournal(plan.case_dir)
            state = journal.read_state()

            self.assertEqual(
                state.status,  # type: ignore[union-attr]  # mypy doesn't know state can be None but in this test it won't be
                "FAILED",
            )
            self.assertEqual(
                state.postprocess_status,  # type: ignore[union-attr]  # mypy doesn't know state can be None but in this test it won't be
                "FAILED",
            )
            self.assertIn(
                "simulated steady-state failure",
                state.error,  # type: ignore[arg-type, union-attr]  # mypy doesn't know state can be None but in this test it won't be
            )

    def test_run_one_case_returns_failure_when_case_dir_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            model_path = root_dir / "base_model.wdi"
            model_path.write_bytes(b"base_model")

            model_spec = ModelSpecification(
                model_path=model_path,
                wanda_bin=Path(r"c:\wanda\bin"),
                base_model_name="base_model",
                reuse_existing_data=True,
                run_steady=False,
                run_unsteady=False,
            )
            scenario = ScenarioSpecification(
                meta=ScenarioMeta.model_validate(
                    {
                        "Number": 1,
                        "Include": True,
                        "Name": "case_locked",
                    }
                )
            )
            plan = CasePlan(
                case_id="case_locked",
                case_dir=root_dir / "scenarios" / "case_locked",
                model_spec=model_spec,
                scenario=scenario,
                adapter_class="unit_test.wanda.fakes:FakeWandaAdapter",
            )

            journal = CaseJournal(plan.case_dir)
            journal.acquire()
            try:
                with patch(
                    "pywandahydra.execution.journal.FileLock",
                    side_effect=lambda path, timeout: FileLock(path, timeout=0),
                ):
                    result = run_one_case(plan)
            finally:
                journal.release()

            self.assertFalse(result["success"])
            self.assertIn("locked", result["error"])


if __name__ == "__main__":
    unittest.main()
