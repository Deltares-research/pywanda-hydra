from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution import runner
from pywandahydra.execution.journal import CaseJournal
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


class TestRunner(unittest.TestCase):
    def _build_ctx(self, root_dir: Path) -> RunContext:
        return RunContext(
            run_id="run_001",
            timestamp="20260101T000000Z",
            root_dir=root_dir / "run_001",
        )

    def _build_model_spec(self, root_dir: Path, *, readonly: bool) -> ModelSpecification:
        model_path = root_dir / "base_model.wdi"
        if not model_path.exists():
            model_path.write_bytes(b"base_model")
        return ModelSpecification(
            model_path=model_path,
            wanda_bin=Path(r"c:\wanda\bin"),
            base_model_name="base_model",
            readonly=readonly,
            run_steady=False,
            run_unsteady=False,
        )

    def _build_scenario(self, name: str) -> ScenarioSpecification:
        return ScenarioSpecification(
            meta=ScenarioMeta.model_validate({"Number": 1, "Include": True, "Name": name})
        )

    def test_run_with_no_scenarios_returns_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._build_ctx(root_dir)
            model_spec = self._build_model_spec(root_dir, readonly=True)

            result = runner.run(
                model=model_spec,
                ctx=ctx,
                scenarios=[],
                persist_manifest=False,
            )

            self.assertEqual(result.run_id, "run_001")
            self.assertEqual(result.n_total, 0)
            self.assertEqual(result.n_selected, 0)
            self.assertEqual(result.n_success, 0)
            self.assertEqual(result.n_failed, 0)
            self.assertEqual(result.results, [])

    def test_run_sequential_with_fake_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._build_ctx(root_dir)
            model_spec = self._build_model_spec(root_dir, readonly=False)
            scenario = self._build_scenario("case_001")

            with (
                patch(
                    "pywandahydra.execution.worker.bootstrap_workflows",
                    return_value=None,
                ),
                patch(
                    "pywandahydra.execution.worker.run_postprocessing",
                    return_value={"summary_table": True},
                ),
            ):
                result = runner.run(
                    model=model_spec,
                    ctx=ctx,
                    scenarios=[scenario],
                    persist_manifest=True,
                    adapter_class="unit_test.wanda.fakes:FakeWandaAdapter",
                )

            self.assertEqual(result.n_total, 1)
            self.assertEqual(result.n_selected, 1)
            self.assertEqual(result.n_success, 1)
            self.assertEqual(result.n_failed, 0)
            self.assertEqual(len(result.results), 1)
            self.assertTrue(result.results[0]["success"])

            run_root = ctx.root_dir
            self.assertTrue((run_root / "scenarios" / "case_001").exists())
            log_files = list((run_root / "logs").glob("*_log_*.json"))
            self.assertEqual(len(log_files), 1)

    def test_run_resume_skips_completed_readonly_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._build_ctx(root_dir)
            model_spec = self._build_model_spec(root_dir, readonly=True)
            scenario = self._build_scenario("case_001")

            case_dir = ctx.root_dir / "scenarios" / "case_001"
            with (
                patch(
                    "pywandahydra.execution.worker.bootstrap_workflows",
                    return_value=None,
                ),
                patch(
                    "pywandahydra.execution.worker.run_postprocessing",
                    return_value={"summary_table": True},
                ),
            ):
                first = runner.run(
                    model=model_spec,
                    ctx=ctx,
                    scenarios=[scenario],
                    persist_manifest=False,
                    adapter_class="unit_test.wanda.fakes:FakeWandaAdapter",
                )
            self.assertEqual(first.n_success, 1)

            journal = CaseJournal(case_dir)
            state = journal.read_state()
            assert state is not None
            self.assertEqual(
                state.status,
                "SUCCEEDED",
            )

            with (
                patch(
                    "pywandahydra.execution.worker.bootstrap_workflows",
                    return_value=None,
                ),
                patch(
                    "pywandahydra.execution.worker.run_postprocessing",
                    return_value={"summary_table": True},
                ),
            ):
                second = runner.run(
                    model=model_spec,
                    ctx=ctx,
                    scenarios=[scenario],
                    persist_manifest=False,
                    resume=True,
                    adapter_class="unit_test.wanda.fakes:FakeWandaAdapter",
                )

            self.assertEqual(second.n_skipped, 1)
            self.assertEqual(second.n_success, 0)
            self.assertEqual(second.n_failed, 0)
            self.assertEqual(second.results, [])


if __name__ == "__main__":
    unittest.main()
