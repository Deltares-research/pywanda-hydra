"""Tests for S07 root run preparation and execution bridge."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from pywandahydra.run import execute_run, prepare_run, validate_run
from pywandahydra.scenarios import AnalysisMeta, ScenarioSpecification


def _write_configuration(tmp_path: Path) -> Path:
    (tmp_path / "bin").mkdir()
    (tmp_path / "model.wdi").write_bytes(b"model")
    (tmp_path / "scenarios.xlsx").write_bytes(b"scenarios")
    path = tmp_path / "run.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "run_id": "run_001",
                "output_root": "runs",
                "scenario_file": "scenarios.xlsx",
                "model": {"path": "model.wdi", "wanda_bin": "bin"},
                "simulation": {"steady": False, "unsteady": False},
                "execution": {"workers": 1, "resume": False},
                "outputs": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def _document(path: Path, *names: str) -> SimpleNamespace:
    scenarios = tuple(
        ScenarioSpecification(number=index, include=True, name=name)
        for index, name in enumerate(names, 1)
    )
    return SimpleNamespace(scenarios=scenarios, analysis_metadata=AnalysisMeta(), source_path=path)


def test_prepare_run_resolves_paths_without_writing(tmp_path: Path) -> None:
    path = _write_configuration(tmp_path)
    document = _document(tmp_path / "scenarios.xlsx", "case_one")

    with patch("pywandahydra.run.load_scenario_document", return_value=document):
        plan = prepare_run(path)

    assert plan.configuration.model.path == Path("model.wdi")
    assert plan.model_path == tmp_path / "model.wdi"
    assert plan.run_dir == tmp_path / "runs" / "run_001"
    assert len(plan.cases) == 1
    assert not plan.run_dir.exists()


def test_prepare_run_validates_case_names(tmp_path: Path) -> None:
    path = _write_configuration(tmp_path)
    document = _document(tmp_path / "scenarios.xlsx", "../unsafe")

    with patch("pywandahydra.run.load_scenario_document", return_value=document):
        with pytest.raises(ValueError, match="safe path names"):
            prepare_run(path, workers=2, resume=True)


def test_validate_run_is_wanda_free_by_default(tmp_path: Path) -> None:
    path = _write_configuration(tmp_path)
    document = _document(tmp_path / "scenarios.xlsx", "case_one")

    with (
        patch("pywandahydra.run.load_scenario_document", return_value=document),
        patch("pywandahydra.wanda.validation.assert_preflight_valid") as preflight,
    ):
        validate_run(path)

    preflight.assert_not_called()


def test_execute_run_delegates_to_current_runner(tmp_path: Path) -> None:
    path = _write_configuration(tmp_path)
    document = _document(tmp_path / "scenarios.xlsx", "case_one")
    expected = object()

    with patch("pywandahydra.run.load_scenario_document", return_value=document):
        plan = prepare_run(path)
    with patch("pywandahydra.execution.runner.run", return_value=expected) as runner:
        assert execute_run(plan) is expected

    assert runner.call_args.kwargs["model"].model_path == tmp_path / "model.wdi"
