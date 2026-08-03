from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from pywandahydra.config.loader import ExecutionConfig
from pywandahydra.postprocessing.core.context import CaseContext, PostProcessingRunContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.workflows import bootstrap
from pywandahydra.postprocessing.workflows.base import resolve_workflow
from pywandahydra.scenarios import ScenarioSpecification


class TestWorkflowConfig(unittest.TestCase):
    def test_execution_config_accepts_bare_workflow_string(self) -> None:
        cfg = ExecutionConfig.model_validate({"workflow": "default"})
        self.assertEqual(cfg.workflow.name, "default")
        self.assertEqual(cfg.workflow.params, {})

    def test_resolve_workflow_rejects_unknown(self) -> None:
        bootstrap()
        with self.assertRaises(KeyError):
            resolve_workflow("does_not_exist")

    def test_resolve_workflow_rejects_extra_params(self) -> None:
        bootstrap()
        with self.assertRaises(ValidationError):
            resolve_workflow("default", {"unexpected": 1})

    def test_config_driven_workflow_builds_case_and_run_steps(self) -> None:
        bootstrap()

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            case_dir = root / "scenarios" / "case_001"
            case_dir.mkdir(parents=True, exist_ok=True)

            scenario = ScenarioSpecification(
                number=1,
                include=True,
                name="case_001",
            )
            case_ctx = CaseContext(
                cache=ParquetCache(case_dir),
                scenario=scenario,
                case_dir=case_dir,
            )
            post_processing_run_ctx = PostProcessingRunContext(
                run_root=root, run_id="run_001", case_results=tuple()
            )

            workflow = resolve_workflow(
                "composed",
                {
                    "case_steps": [{"name": "summary_table"}],
                    "run_steps": [{"name": "aggregate_tables"}],
                },
            )

            self.assertEqual([s.name for s in workflow.case_steps(case_ctx)], ["summary_table"])
            self.assertEqual(
                [s.name for s in workflow.run_steps(post_processing_run_ctx)],
                ["aggregate_tables"],
            )

