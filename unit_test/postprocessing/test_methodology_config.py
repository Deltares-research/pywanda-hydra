from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from pywandahydra.config.loader import ExecutionConfig
from pywandahydra.postprocessing.cache import ParquetCache
from pywandahydra.postprocessing.context import CaseContext, RunStepContext
from pywandahydra.postprocessing.methodologies import bootstrap
from pywandahydra.postprocessing.methodologies.base import resolve_methodology
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


class TestMethodologyConfig(unittest.TestCase):
    def test_execution_config_accepts_bare_methodology_string(self) -> None:
        cfg = ExecutionConfig.model_validate({"methodology": "default"})
        self.assertEqual(cfg.methodology.name, "default")
        self.assertEqual(cfg.methodology.params, {})

    def test_resolve_methodology_rejects_unknown(self) -> None:
        bootstrap()
        with self.assertRaises(KeyError):
            resolve_methodology("does_not_exist")

    def test_resolve_methodology_rejects_extra_params(self) -> None:
        bootstrap()
        with self.assertRaises(ValidationError):
            resolve_methodology("default", {"unexpected": 1})

    def test_composed_methodology_builds_case_and_run_steps(self) -> None:
        bootstrap()

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            case_dir = root / "scenarios" / "case_001"
            case_dir.mkdir(parents=True, exist_ok=True)

            scenario = ScenarioSpecification(
                meta=ScenarioMeta.model_validate(
                    {
                        "Number": 1,
                        "Include": True,
                        "Name": "case_001",
                    }
                )
            )
            case_ctx = CaseContext(
                cache=ParquetCache(case_dir),
                scenario=scenario,
                case_dir=case_dir,
            )
            run_ctx = RunStepContext(
                run_root=root, run_id="run_001", case_results=tuple()
            )

            meth = resolve_methodology(
                "composed",
                {
                    "case_steps": [{"name": "summary_table"}],
                    "run_steps": [{"name": "aggregate_tables"}],
                },
            )

            self.assertEqual(
                [s.name for s in meth.case_steps(case_ctx)], ["summary_table"]
            )
            self.assertEqual(
                [s.name for s in meth.run_steps(run_ctx)], ["aggregate_tables"]
            )
