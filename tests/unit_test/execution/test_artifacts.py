from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.artifacts import create_run_directories, write_run_log
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


class TestCreateRunDirectories(unittest.TestCase):
    def _ctx(self, root_dir: Path) -> RunContext:
        return RunContext(
            run_id="run_001",
            timestamp="2026-01-01T00:00:00Z",
            root_dir=root_dir / "run_001",
        )

    def test_creates_expected_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._ctx(root_dir)

            create_run_directories(ctx)

            for name in ("figures", "logs", "tables", "scenarios"):
                self.assertTrue((ctx.root_dir / name).is_dir())

    def test_copies_config_file_when_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._ctx(root_dir)
            config_path = root_dir / "config.yaml"
            config_path.write_text("model: {}", encoding="utf-8")

            create_run_directories(ctx, config_path=config_path)

            self.assertTrue((ctx.root_dir / "config.yaml").exists())

    def test_copies_scenario_file_when_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = self._ctx(root_dir)

            for scenario_name in ("scenarios.xls", "scenarios.xlsx", "scenarios.csv"):
                with self.subTest(scenario_name=scenario_name):
                    scenario_file = root_dir / scenario_name
                    scenario_file.write_bytes(b"scenario data")

                    create_run_directories(ctx, scenario_file=scenario_file)

                    self.assertTrue((ctx.root_dir / scenario_name).exists())


class TestWriteRunLog(unittest.TestCase):
    def test_writes_json_log_with_expected_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_dir = Path(tmp_dir)
            ctx = RunContext(
                run_id="run_001",
                timestamp="20260101T000000Z",
                root_dir=root_dir / "run_001",
            )
            (ctx.root_dir / "logs").mkdir(parents=True)

            model_path = root_dir / "base_model.wdi"
            model_path.write_bytes(b"model")
            model_spec = ModelSpecification(
                model_path=model_path,
                wanda_bin=Path(r"c:\wanda\bin"),
                base_model_name="base_model",
            )
            scenario = ScenarioSpecification(
                meta=ScenarioMeta.model_validate({"Number": 1, "Include": True, "Name": "case_001"})
            )

            write_run_log(
                context_object=ctx,
                model_spec=model_spec,
                scenarios=[scenario],
            )

            log_path = ctx.root_dir / "logs" / "run_001_log_20260101T000000Z.json"
            self.assertTrue(log_path.exists())

            with log_path.open(encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["run_context"]["run_id"], "run_001")
            self.assertEqual(data["model_specification"]["base_model_name"], "base_model")
            self.assertEqual(len(data["scenarios"]), 1)
            self.assertEqual(data["scenarios"][0]["meta"]["name"], "case_001")


if __name__ == "__main__":
    unittest.main()
