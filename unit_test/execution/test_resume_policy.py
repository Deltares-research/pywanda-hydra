from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pywandahydra.config.models import ModelSpecification
from pywandahydra.execution.case_plan import CasePlan
from pywandahydra.execution.journal import CaseJournal, resume_decision
from pywandahydra.execution.worker import run_one_case
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


class TestResumePolicy(unittest.TestCase):
    def _build_plan(
        self, *, root_dir: Path, readonly: bool, case_name: str = "case_001"
    ) -> CasePlan:
        model_spec = ModelSpecification(
            model_path=root_dir / "base_model.wdi",
            wanda_bin=r"c:\\wanda\\bin\\",
            base_model_name="base_model",
            readonly=readonly,
            run_steady=False,
            run_unsteady=False,
        )
        scenario = ScenarioSpecification(
            meta=ScenarioMeta.model_validate(
                {
                    "Number": 1,
                    "Include": True,
                    "Name": case_name,
                }
            )
        )
        return CasePlan(
            case_id=case_name,
            case_dir=root_dir / "scenarios" / case_name,
            model_spec=model_spec,
            scenario=scenario,
        )

    def test_resume_decision_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            plan = self._build_plan(root_dir=tmp_path, readonly=True)
            journal = CaseJournal(plan.case_dir)

            self.assertEqual(
                resume_decision(
                    journal=journal,
                    config_hash=plan.config_hash,
                    readonly=True,
                ),
                "run",
            )

            with journal:
                journal.transition(
                    "SUCCEEDED",
                    config_hash=plan.config_hash,
                )

            self.assertEqual(
                resume_decision(
                    journal=journal,
                    config_hash=plan.config_hash,
                    readonly=True,
                ),
                "skip",
            )
            self.assertEqual(
                resume_decision(
                    journal=journal,
                    config_hash=plan.config_hash,
                    readonly=False,
                ),
                "rerun",
            )
            self.assertEqual(
                resume_decision(
                    journal=journal,
                    config_hash="sha256:different",
                    readonly=True,
                ),
                "run",
            )

    def test_worker_uses_shared_skip_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            plan = self._build_plan(root_dir=tmp_path, readonly=True)
            journal = CaseJournal(plan.case_dir)

            with journal:
                journal.transition(
                    "SUCCEEDED",
                    config_hash=plan.config_hash,
                )

            with patch(
                "pywandahydra.execution.worker.bootstrap_methodologies",
                return_value=None,
            ):
                result = run_one_case(plan)

            self.assertTrue(result["success"])
            self.assertTrue(result["skipped"])
            self.assertEqual(result["case_id"], plan.case_id)
            self.assertEqual(result["scenario_dir"], str(plan.case_dir))
