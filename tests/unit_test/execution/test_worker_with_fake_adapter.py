from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pywandahydra.execution.case_plan import CasePlan
from pywandahydra.execution.legacy import ModelSpecification
from pywandahydra.execution.worker import run_one_case
from pywandahydra.scenarios import ScenarioSpecification
from unit_test.wanda.fakes import FakeWandaModelAccess


class TestWorkerWithFakeAdapter(unittest.TestCase):
    def test_run_one_case_works_with_fake_adapter(self) -> None:
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
                run_unsteady=True,
            )
            scenario = ScenarioSpecification(
                number=1,
                include=True,
                name="case_fake",
            )
            plan = CasePlan(
                case_id="case_fake",
                case_dir=root_dir / "scenarios" / "case_fake",
                model_spec=model_spec,
                scenario=scenario,
            )

            with patch(
                "pywandahydra.execution.worker.bootstrap_workflows",
                return_value=None,
            ):
                with (
                    patch(
                        "pywandahydra.execution.worker._build_model_access",
                        return_value=FakeWandaModelAccess(),
                    ),
                    patch(
                        "pywandahydra.execution.worker.run_postprocessing",
                        return_value={"summary_table": True},
                    ),
                ):
                    result = run_one_case(plan)

            self.assertTrue(result["success"])
            self.assertEqual(result["case_id"], "case_fake")
            self.assertEqual(result["scenario_dir"], str(plan.case_dir))
