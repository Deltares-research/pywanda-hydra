"""Tests for run_optimization outputs and result writers."""

from __future__ import annotations

import json
from pathlib import Path

from pywandahydra.optimization.runner import run_optimization

from .conftest import SyntheticEvaluator, make_config


def test_run_optimization_writes_outputs(tmp_path: Path) -> None:
    cfg = make_config(output_root=str(tmp_path), run_id="run_x")
    results = run_optimization(cfg, evaluator=SyntheticEvaluator(), c_unit="J")

    run_root = tmp_path / "run_x"
    json_path = run_root / "optimization_results.json"
    csv_path = run_root / "optimization_results.csv"
    plot_path = run_root / "figures" / "acceptable_c_range.png"
    config_dump = run_root / "optimization_config.json"

    assert json_path.exists()
    assert csv_path.exists()
    assert plot_path.exists()
    assert config_dump.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run_x"
    assert payload["min_feasible_vessels"] == results.min_feasible_vessels == 8
    assert len(payload["vessels"]) == 10


def test_run_optimization_no_plot(tmp_path: Path) -> None:
    cfg = make_config(output_root=str(tmp_path), run_id="run_np")
    run_optimization(cfg, evaluator=SyntheticEvaluator(), render_plot=False)
    plot_path = tmp_path / "run_np" / "figures" / "acceptable_c_range.png"
    assert not plot_path.exists()


def test_csv_has_one_row_per_vessel_count(tmp_path: Path) -> None:
    cfg = make_config(output_root=str(tmp_path), run_id="run_csv")
    run_optimization(cfg, evaluator=SyntheticEvaluator(), render_plot=False)
    csv_text = (tmp_path / "run_csv" / "optimization_results.csv").read_text(encoding="utf-8")
    lines = [line for line in csv_text.splitlines() if line.strip()]
    # header + 10 vessel counts
    assert len(lines) == 11
    assert lines[0].startswith("n_vessels,")
