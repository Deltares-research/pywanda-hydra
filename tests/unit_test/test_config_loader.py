"""Unit tests for run configuration loading and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from pywandahydra.config.loader import (
    RunConfig,
    apply_post_processing_overrides,
    build_run_context,
    config_hash,
    load_run_config,
    validate_run_paths,
)
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


def _minimal_config_dict(*, model_path: str, wanda_bin: str, scenario_file: str) -> dict:
    return {
        "model": {
            "model_path": model_path,
            "wanda_bin": wanda_bin,
            "base_model_name": "base_model",
        },
        "scenario_file": scenario_file,
    }


class TestLoadRunConfig(unittest.TestCase):
    def test_load_yaml_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    _minimal_config_dict(
                        model_path="model.wdi",
                        wanda_bin="bin",
                        scenario_file="scenarios.xls",
                    )
                ),
                encoding="utf-8",
            )

            cfg = load_run_config(config_path)

            self.assertEqual(cfg.model.base_model_name, "base_model")
            self.assertEqual(cfg.execution.n_workers, 1)

    def test_load_json_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_path = tmp_path / "config.json"
            config_path.write_text(
                json.dumps(
                    _minimal_config_dict(
                        model_path="model.wdi",
                        wanda_bin="bin",
                        scenario_file="scenarios.xls",
                    )
                ),
                encoding="utf-8",
            )

            cfg = load_run_config(config_path)

            self.assertEqual(cfg.scenario_file, Path("scenarios.xls"))

    def test_missing_file_raises_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "does_not_exist.yaml"

            with self.assertRaises(FileNotFoundError):
                load_run_config(missing)

    def test_unsupported_extension_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.txt"
            config_path.write_text("model: {}", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_run_config(config_path)

            self.assertIn("Unsupported config format", str(ctx.exception))

    def test_non_mapping_content_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            config_path.write_text("- a\n- b\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_run_config(config_path)

            self.assertIn("must contain a mapping", str(ctx.exception))

    def test_bare_workflow_string_is_coerced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            data = _minimal_config_dict(
                model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
            )
            data["execution"] = {"workflow": "default"}
            config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

            cfg = load_run_config(config_path)

            self.assertEqual(cfg.execution.workflow.name, "default")

    def test_custom_extractors_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            data = _minimal_config_dict(
                model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
            )
            data["execution"] = {"extractors": [{"name": "external"}]}
            config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_run_config(config_path)

            self.assertIn("extractors", str(ctx.exception))


class TestValidateRunPaths(unittest.TestCase):
    def _write_config(self, tmp_path: Path) -> tuple[RunConfig, Path]:
        model_dir = tmp_path
        model_path = model_dir / "model.wdi"
        model_path.write_bytes(b"model")
        wanda_bin = model_dir / "bin"
        wanda_bin.mkdir()
        scenario_file = model_dir / "scenarios.xls"
        scenario_file.write_bytes(b"scenarios")

        cfg = RunConfig.model_validate(
            _minimal_config_dict(
                model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
            )
            | {"output_root": "runs"}
        )
        return cfg, tmp_path

    def test_validate_resolves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg, tmp_path = self._write_config(Path(tmp_dir))

            validate_run_paths(cfg, config_dir=tmp_path)

            self.assertTrue(cfg.model.model_path.is_absolute())
            self.assertEqual(cfg.model.model_path, tmp_path / "model.wdi")
            self.assertTrue(cfg.output_root.exists())

    def test_validate_rejects_non_wdi_model_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.txt").write_bytes(b"model")
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            cfg = RunConfig.model_validate(
                _minimal_config_dict(
                    model_path="model.txt",
                    wanda_bin="bin",
                    scenario_file="scenarios.xls",
                )
            )

            with self.assertRaises(ValueError) as ctx:
                validate_run_paths(cfg, config_dir=tmp_path)

            self.assertIn(".wdi", str(ctx.exception))

    def test_validate_rejects_missing_model_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            cfg = RunConfig.model_validate(
                _minimal_config_dict(
                    model_path="missing.wdi",
                    wanda_bin="bin",
                    scenario_file="scenarios.xls",
                )
            )

            with self.assertRaises(ValueError) as ctx:
                validate_run_paths(cfg, config_dir=tmp_path)

            self.assertIn("does not exist", str(ctx.exception))

    def test_validate_rejects_missing_wanda_bin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.wdi").write_bytes(b"model")
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            cfg = RunConfig.model_validate(
                _minimal_config_dict(
                    model_path="model.wdi",
                    wanda_bin="missing_bin",
                    scenario_file="scenarios.xls",
                )
            )

            with self.assertRaises(ValueError) as ctx:
                validate_run_paths(cfg, config_dir=tmp_path)

            self.assertIn("wanda_bin", str(ctx.exception))

    def test_validate_rejects_missing_scenario_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.wdi").write_bytes(b"model")
            (tmp_path / "bin").mkdir()

            cfg = RunConfig.model_validate(
                _minimal_config_dict(
                    model_path="model.wdi",
                    wanda_bin="bin",
                    scenario_file="missing.xls",
                )
            )

            with self.assertRaises(ValueError) as ctx:
                validate_run_paths(cfg, config_dir=tmp_path)

            self.assertIn("scenario_file", str(ctx.exception))


class TestApplyPostProcessingOverrides(unittest.TestCase):
    def _scenario(self) -> ScenarioSpecification:
        return ScenarioSpecification(
            meta=ScenarioMeta.model_validate({"Number": 1, "Include": True, "Name": "case_001"})
        )

    def test_no_theme_configured_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.wdi").write_bytes(b"model")
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            cfg = RunConfig.model_validate(
                _minimal_config_dict(
                    model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
                )
            )
            scenario = self._scenario()
            original_theme = scenario.post_processing.theme

            apply_post_processing_overrides(cfg, [scenario])

            self.assertEqual(scenario.post_processing.theme, original_theme)

    def test_known_theme_overrides_scenario_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.wdi").write_bytes(b"model")
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            data = _minimal_config_dict(
                model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
            )
            data["post_processing"] = {"theme": "deltares_light"}
            cfg = RunConfig.model_validate(data)
            scenario = self._scenario()

            apply_post_processing_overrides(cfg, [scenario])

            self.assertEqual(scenario.post_processing.theme, "deltares_light")

    def test_unknown_theme_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "model.wdi").write_bytes(b"model")
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            data = _minimal_config_dict(
                model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
            )
            data["post_processing"] = {"theme": "does_not_exist"}
            cfg = RunConfig.model_validate(data)

            with self.assertRaises(ValueError) as ctx:
                apply_post_processing_overrides(cfg, [self._scenario()])

            self.assertIn("not registered", str(ctx.exception))


class TestConfigHashAndRunContext(unittest.TestCase):
    def _cfg(self, run_id: str = "run_001") -> RunConfig:
        data = _minimal_config_dict(
            model_path="model.wdi", wanda_bin="bin", scenario_file="scenarios.xls"
        )
        data["run_id"] = run_id
        return RunConfig.model_validate(data)

    def test_config_hash_is_deterministic(self) -> None:
        cfg_a = self._cfg()
        cfg_b = self._cfg()

        self.assertEqual(config_hash(cfg_a), config_hash(cfg_b))
        self.assertTrue(config_hash(cfg_a).startswith("sha256:"))

    def test_config_hash_differs_for_different_run_id(self) -> None:
        cfg_a = self._cfg(run_id="run_001")
        cfg_b = self._cfg(run_id="run_002")

        self.assertNotEqual(config_hash(cfg_a), config_hash(cfg_b))

    def test_build_run_context_uses_output_root_and_run_id(self) -> None:
        cfg = self._cfg(run_id="run_001")

        ctx = build_run_context(cfg)

        self.assertEqual(ctx.run_id, "run_001")
        self.assertEqual(ctx.root_dir, cfg.output_root / "run_001")


if __name__ == "__main__":
    unittest.main()
