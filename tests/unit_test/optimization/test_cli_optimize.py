"""Smoke tests for the `optimize` CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from pywandahydra.cli.commands import app
from pywandahydra.optimization.results import OptimizationResults

runner = CliRunner()


def _write_config(tmp_path: Path, **overrides: object) -> Path:
    (tmp_path / "bin").mkdir()
    (tmp_path / "base.wdi").write_bytes(b"model")
    payload: dict = {
        "run_id": "cli_run",
        "output_root": "runs",
        "model": {
            "model_path": "base.wdi",
            "wanda_bin": "bin",
            "base_model_name": "base",
        },
        "surge_vessel": "SURGE",
        "pressure_pipes_keyword": "PIPE",
        "acceptance": {"min_pressure": 0.0, "min_water_level": 20.3},
        "number_of_vessels": {"min": 1, "max": 4},
        "c_value": {"lower": 2.5e6, "upper": 30e6},
    }
    payload.update(overrides)
    config_path = tmp_path / "opt.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def test_optimize_success(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    fake = OptimizationResults(run_id="cli_run", vessels=[], min_feasible_vessels=3)

    with (
        patch("pywandahydra.cli.commands.faulthandler.enable"),
        patch("pywandahydra.optimization.runner.run_optimization", return_value=fake) as mock,
    ):
        result = runner.invoke(app, ["optimize", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "minimum feasible number of surge vessels = 3" in result.output
    mock.assert_called_once()


def test_optimize_no_feasible(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    fake = OptimizationResults(run_id="cli_run", vessels=[], min_feasible_vessels=None)

    with (
        patch("pywandahydra.cli.commands.faulthandler.enable"),
        patch("pywandahydra.optimization.runner.run_optimization", return_value=fake),
    ):
        result = runner.invoke(app, ["optimize", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "no feasible surge-vessel count found" in result.output


def test_optimize_invalid_config(tmp_path: Path) -> None:
    # Missing required fields -> load/validation error, exit code 1.
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"surge_vessel": "SURGE"}), encoding="utf-8")
    with patch("pywandahydra.cli.commands.faulthandler.enable"):
        result = runner.invoke(app, ["optimize", str(bad)])
    assert result.exit_code == 1
    assert "Error loading config" in result.output


def test_optimize_bad_model_path(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        model={"model_path": "missing.wdi", "wanda_bin": "bin", "base_model_name": "base"},
    )
    with patch("pywandahydra.cli.commands.faulthandler.enable"):
        result = runner.invoke(app, ["optimize", str(config_path)])
    assert result.exit_code == 1
    assert "Invalid runtime configuration" in result.output
