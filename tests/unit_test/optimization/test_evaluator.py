"""Tests for scenario building and metric reading."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from pywandahydra.optimization.evaluator import (
    WandaEvaluator,
    _classify_failure,
    build_scenario,
)
from pywandahydra.optimization.metrics import read_min_metrics
from pywandahydra.postprocessing.io.cache import ParquetCache

from .conftest import make_config


def test_build_scenario_parameters_and_outputs() -> None:
    cfg = make_config(
        base_parameters=[{"component": "TAP03", "property": "Discharge", "value": 0.05}]
    )
    scenario = build_scenario(cfg, n_vessels=3, c_value=1.25e7, laplace=1.4)

    props = {(p.component, p.property): p.value for p in scenario.parameters}
    assert props[("SURGE", "Number of vessels")] == 3
    assert props[("SURGE", "Initial C in P*V=C")] == 1.25e7
    assert props[("SURGE", "Laplace coefficient")] == 1.4
    # Base parameters are preserved.
    assert props[("TAP03", "Discharge")] == 0.05

    table_keys = {(t.component, t.property) for t in scenario.post_processing.tables}
    assert ("SURGE", "Fluid level") in table_keys
    assert ("PIPE", "Pressure") in table_keys
    assert scenario.meta.include is True


def test_build_scenario_names_are_deterministic() -> None:
    cfg = make_config()
    a = build_scenario(cfg, 2, 1e7, 1.0).meta.name
    b = build_scenario(cfg, 2, 1e7, 1.0).meta.name
    c = build_scenario(cfg, 2, 2e7, 1.0).meta.name
    assert a == b
    assert a != c


def test_read_min_metrics(tmp_path: Path) -> None:
    cols = pd.MultiIndex.from_tuples(
        [
            ("PIPE1", "Pressure", 0.0),
            ("PIPE1", "Pressure", 10.0),
            ("SURGE", "Fluid level", float("nan")),
        ],
        names=["component", "property", "s_location"],
    )
    df = pd.DataFrame([[3.0, 2.0, 21.0], [1.5, 5.0, 20.0]], columns=cols)

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    ParquetCache(case_dir).write({"components": df, "routes": {}, "resolution": {}})

    min_pressure, min_water_level = read_min_metrics(case_dir, "Pressure", "Fluid level")
    assert min_pressure == 1.5
    assert min_water_level == 20.0


def test_read_min_metrics_missing_property(tmp_path: Path) -> None:
    case_dir = tmp_path / "empty"
    case_dir.mkdir()
    min_pressure, min_water_level = read_min_metrics(case_dir, "Pressure", "Fluid level")
    assert min_pressure != min_pressure  # nan
    assert min_water_level != min_water_level  # nan


def test_classify_failure_matches_case_insensitive() -> None:
    patterns = ["Empty"]
    assert _classify_failure("Unsteady error in physical component: AIRVin A1 Empty", patterns)
    assert _classify_failure("component is EMPTY now", patterns)
    assert not _classify_failure("Convergence not reached", patterns)


def test_classify_failure_no_patterns() -> None:
    assert not _classify_failure("AIRVin A1 Empty", [])


def test_wanda_evaluator_drainage_rejects_water_level_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_path = tmp_path / "base.wdi"
    model_path.write_bytes(b"dummy")
    cfg = make_config(
        model={
            "model_path": str(model_path),
            "wanda_bin": "./bin",
            "base_model_name": "base",
        }
    )
    evaluator = WandaEvaluator(cfg, run_root=tmp_path)

    def fake_run_one_case(plan: object) -> dict:
        return {
            "success": False,
            "error": "Unsteady error in physical component: AIRVin A1 Empty",
        }

    monkeypatch.setattr(
        "pywandahydra.optimization.evaluator.run_one_case", fake_run_one_case
    )

    result = evaluator.run(n_vessels=2, c_value=1e7, laplace=1.0)
    assert result.failed is True
    assert result.error is not None
    assert "Empty" in result.error
    # Drainage is a high-C / water-level limit, not a pressure failure.
    assert result.min_pressure == math.inf
    assert result.min_water_level == -math.inf


def test_wanda_evaluator_untolerated_failure_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_path = tmp_path / "base.wdi"
    model_path.write_bytes(b"dummy")
    cfg = make_config(
        model={
            "model_path": str(model_path),
            "wanda_bin": "./bin",
            "base_model_name": "base",
        }
    )
    evaluator = WandaEvaluator(cfg, run_root=tmp_path)

    def fake_run_one_case(plan: object) -> dict:
        return {"success": False, "error": "Convergence not reached"}

    monkeypatch.setattr(
        "pywandahydra.optimization.evaluator.run_one_case", fake_run_one_case
    )

    with pytest.raises(RuntimeError, match="Convergence not reached"):
        evaluator.run(n_vessels=2, c_value=1e7, laplace=1.0)

