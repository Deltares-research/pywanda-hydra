"""Tests for authored run configuration parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pywandahydra.config import RunConfiguration, load_run_config


def _configuration() -> dict[str, object]:
    return {
        "run_id": "run_001",
        "output_root": "runs",
        "scenario_file": "scenarios.xlsx",
        "model": {"path": "model.wdi", "wanda_bin": "bin"},
        "simulation": {"steady": True, "unsteady": False},
        "execution": {"workers": 2, "resume": True},
        "outputs": {"figure_formats": ["pdf"], "table_formats": ["csv"]},
    }


def test_load_yaml_configuration(tmp_path: Path) -> None:
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(_configuration()), encoding="utf-8")

    configuration = load_run_config(path)

    assert configuration.execution.workers == 2
    assert configuration.model.path == Path("model.wdi")
    assert configuration.outputs.figure_formats == ("pdf",)


def test_load_json_configuration(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(_configuration()), encoding="utf-8")

    assert load_run_config(path).run_id == "run_001"


def test_rejects_removed_authored_keys() -> None:
    data = _configuration()
    data["model"] = {"path": "model.wdi", "wanda_bin": "bin", "base_model_name": "model"}

    with pytest.raises(ValueError, match="base_model_name"):
        RunConfiguration.model_validate(data)


def test_rejects_non_mapping_configuration(tmp_path: Path) -> None:
    path = tmp_path / "run.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a mapping"):
        load_run_config(path)
