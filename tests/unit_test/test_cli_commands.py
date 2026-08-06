"""Focused tests for the S07 CLI wrappers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from pywandahydra.cli.commands import app
from pywandahydra.execution.outcomes import CaseResult, RunResult

runner = CliRunner()


def test_run_delegates_to_root_api(tmp_path: Path) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text("run_id: run\n", encoding="utf-8")
    plan = SimpleNamespace(cases=(object(), object()))
    result = RunResult(
        "run",
        (
            CaseResult("one", "simulate", True),
            CaseResult("two", "simulate", True),
        ),
    )

    with (
        patch("pywandahydra.run.prepare_run", return_value=plan) as prepare,
        patch("pywandahydra.run.execute_run", return_value=result),
        patch("pywandahydra.cli.commands.faulthandler.enable"),
    ):
        invocation = runner.invoke(app, ["run", str(config_path), "--workers", "2", "--resume"])

    assert invocation.exit_code == 0
    prepare.assert_called_once_with(config_path, workers=2, resume=True, preflight=True)
    assert "Run complete: 2 succeeded" in invocation.output


def test_validate_delegates_to_root_api(tmp_path: Path) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text("run_id: run\n", encoding="utf-8")
    plan = SimpleNamespace(
        configuration=SimpleNamespace(run_id="run", execution=SimpleNamespace(workers=1)),
        scenario_document=SimpleNamespace(scenarios=(object(),)),
        cases=(object(),),
    )

    with patch("pywandahydra.run.validate_run", return_value=plan) as validate:
        invocation = runner.invoke(app, ["validate", str(config_path)])

    assert invocation.exit_code == 0
    validate.assert_called_once_with(config_path)
    assert "Validation passed." in invocation.output
