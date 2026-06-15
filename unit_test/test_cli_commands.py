"""Smoke tests for the pywandahydra CLI commands.

These exercise the typer app via CliRunner without requiring WANDA —
covering argument parsing, error handling, and output formatting for
the `status`, `validate`, and `plugins` subcommands.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from pywandahydra.cli.commands import app
from pywandahydra.execution.journal import CaseJournal
from pywandahydra.execution.runner import RunResult

runner = CliRunner()


def _write_run_config(tmp_dir: str) -> Path:
    """Write a minimal but path-valid run config and return its path."""
    tmp_path = Path(tmp_dir)
    (tmp_path / "bin").mkdir()
    (tmp_path / "model.wdi").write_bytes(b"model")
    (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {
                    "model_path": "model.wdi",
                    "wanda_bin": "bin",
                    "base_model_name": "base_model",
                },
                "scenario_file": "scenarios.xls",
            }
        ),
        encoding="utf-8",
    )
    return config_path


class TestStatusCommand(unittest.TestCase):
    def test_status_errors_when_no_scenarios_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = runner.invoke(app, ["status", tmp_dir])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("No scenarios directory found", result.output)

    def test_status_reports_no_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "scenarios").mkdir()

            result = runner.invoke(app, ["status", tmp_dir])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("No cases found", result.output)

    def test_status_reports_case_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_dir = Path(tmp_dir) / "scenarios" / "case_001"
            journal = CaseJournal(case_dir)
            with journal:
                journal.transition(
                    "SUCCEEDED",
                    duration_s=1.23,
                    postprocess_status="DONE",
                    config_hash="sha256:abc",
                )

            result = runner.invoke(app, ["status", tmp_dir])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("case_001", result.output)
            self.assertIn("SUCCEEDED", result.output)
            self.assertIn("DONE", result.output)
            self.assertIn("1.2s", result.output)

    def test_status_reports_unknown_for_missing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_dir = Path(tmp_dir) / "scenarios" / "case_002"
            case_dir.mkdir(parents=True)

            result = runner.invoke(app, ["status", tmp_dir])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("case_002", result.output)
            self.assertIn("UNKNOWN", result.output)


class TestRunCommand(unittest.TestCase):
    def test_run_errors_on_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            config_path.write_text("not_a_known_field: 1\n", encoding="utf-8")

            with patch("pywandahydra.cli.commands.faulthandler.enable"):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error loading config", result.output)

    def test_run_errors_on_invalid_workers_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            with patch("pywandahydra.cli.commands.faulthandler.enable"):
                result = runner.invoke(
                    app, ["run", str(config_path), "--workers", "0"]
                )

            self.assertEqual(result.exit_code, 1)
            self.assertIn("--workers must be >= 1", result.output)

    def test_run_errors_on_invalid_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "bin").mkdir()
            # scenario file deliberately missing

            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "model": {
                            "model_path": "missing_model.wdi",
                            "wanda_bin": "bin",
                            "base_model_name": "base_model",
                        },
                        "scenario_file": "scenarios.xls",
                    }
                ),
                encoding="utf-8",
            )

            with patch("pywandahydra.cli.commands.faulthandler.enable"):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid runtime configuration", result.output)

    def test_run_errors_when_scenario_loading_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            with (
                patch("pywandahydra.cli.commands.faulthandler.enable"),
                patch(
                    "pywandahydra.scenarios.mapper.load_scenarios",
                    side_effect=ValueError("bad scenarios"),
                ),
            ):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error loading scenarios", result.output)

    def test_run_errors_when_preflight_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            with (
                patch("pywandahydra.cli.commands.faulthandler.enable"),
                patch("pywandahydra.scenarios.mapper.load_scenarios", return_value=[]),
                patch(
                    "pywandahydra.wanda.validation.assert_preflight_valid",
                    side_effect=ValueError("preflight failed"),
                ),
            ):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("preflight failed", result.output)

    def test_run_errors_when_post_processing_overrides_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            with (
                patch("pywandahydra.cli.commands.faulthandler.enable"),
                patch("pywandahydra.scenarios.mapper.load_scenarios", return_value=[]),
                patch("pywandahydra.wanda.validation.assert_preflight_valid"),
                patch(
                    "pywandahydra.config.loader.apply_post_processing_overrides",
                    side_effect=ValueError("bad post_processing"),
                ),
            ):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid post_processing config", result.output)

    def test_run_completes_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            success_result = RunResult(
                run_id="run-1",
                n_total=1,
                n_selected=1,
                n_success=1,
                n_failed=0,
                n_skipped=0,
                results=[],
            )

            with (
                patch("pywandahydra.cli.commands.faulthandler.enable"),
                patch("pywandahydra.scenarios.mapper.load_scenarios", return_value=[]),
                patch("pywandahydra.wanda.validation.assert_preflight_valid"),
                patch(
                    "pywandahydra.execution.runner.run", return_value=success_result
                ),
            ):
                result = runner.invoke(app, ["run", str(config_path), "--resume"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Run complete: 1 succeeded", result.output)

    def test_run_exits_nonzero_when_cases_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = _write_run_config(tmp_dir)

            failed_result = RunResult(
                run_id="run-1",
                n_total=1,
                n_selected=1,
                n_success=0,
                n_failed=1,
                n_skipped=0,
                results=[],
            )

            with (
                patch("pywandahydra.cli.commands.faulthandler.enable"),
                patch("pywandahydra.scenarios.mapper.load_scenarios", return_value=[]),
                patch("pywandahydra.wanda.validation.assert_preflight_valid"),
                patch(
                    "pywandahydra.execution.runner.run", return_value=failed_result
                ),
            ):
                result = runner.invoke(app, ["run", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("1 failed", result.output)


class TestValidateCommand(unittest.TestCase):
    def test_validate_reports_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            config_path.write_text("not_a_known_field: 1\n", encoding="utf-8")

            result = runner.invoke(app, ["validate", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Config INVALID", result.output)

    def test_validate_reports_invalid_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "bin").mkdir()
            (tmp_path / "scenarios.xls").write_bytes(b"scenarios")

            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "model": {
                            "model_path": "missing_model.wdi",
                            "wanda_bin": "bin",
                            "base_model_name": "base_model",
                        },
                        "scenario_file": "scenarios.xls",
                    }
                ),
                encoding="utf-8",
            )

            result = runner.invoke(app, ["validate", str(config_path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Config OK", result.output)
            self.assertIn("Runtime paths INVALID", result.output)


class TestPluginsCommand(unittest.TestCase):
    def test_plugins_lists_registered_components(self) -> None:
        result = runner.invoke(app, ["plugins"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Extractors:", result.output)
        self.assertIn("Workflows:", result.output)
        self.assertIn("Themes:", result.output)
        self.assertIn("default", result.output)


if __name__ == "__main__":
    unittest.main()
