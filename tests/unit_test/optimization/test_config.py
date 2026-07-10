"""Tests for the optimization config schema and loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pywandahydra.optimization.config import (
    OptimizationConfig,
    VesselCountRange,
    load_optimization_config,
    validate_optimization_paths,
)

from .conftest import make_config


def test_vessel_count_values() -> None:
    assert VesselCountRange(min=1, max=8, step=1).values() == [1, 2, 3, 4, 5, 6, 7, 8]
    assert VesselCountRange(min=2, max=8, step=2).values() == [2, 4, 6, 8]


def test_vessel_count_bad_order() -> None:
    with pytest.raises(ValidationError):
        VesselCountRange(min=5, max=2)


def test_c_value_bad_order() -> None:
    with pytest.raises(ValidationError):
        make_config(c_value={"lower": 30.0, "upper": 1.0})


def test_defaults_applied() -> None:
    cfg = make_config()
    assert cfg.properties.c_value == "Initial C in P*V=C"
    assert cfg.laplace.pressure == 1.4
    assert cfg.laplace.water_level == 1.0
    assert cfg.pressure_property == "Pressure"


def test_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        make_config(unexpected_field=123)


def test_load_optimization_config(tmp_path: Path) -> None:
    payload = {
        "model": {
            "model_path": "./base.wdi",
            "wanda_bin": "./bin",
            "base_model_name": "base",
        },
        "surge_vessel": "SURGE",
        "pressure_pipes_keyword": "PIPE",
        "acceptance": {"min_pressure": 0.0, "min_water_level": 20.3},
        "number_of_vessels": {"min": 1, "max": 4},
        "c_value": {"lower": 2.5e6, "upper": 30e6},
    }
    config_path = tmp_path / "opt.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = load_optimization_config(config_path)
    assert isinstance(cfg, OptimizationConfig)
    assert cfg.surge_vessel == "SURGE"
    assert cfg.number_of_vessels.values() == [1, 2, 3, 4]


def test_load_rejects_non_json(tmp_path: Path) -> None:
    p = tmp_path / "opt.yaml"
    p.write_text("model: {}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported config format"):
        load_optimization_config(p)


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_optimization_config(tmp_path / "nope.json")


def test_validate_paths_missing_model(tmp_path: Path) -> None:
    cfg = make_config(output_root=str(tmp_path))
    with pytest.raises(ValueError, match="model.model_path does not exist"):
        validate_optimization_paths(cfg, config_dir=tmp_path)


def test_validate_paths_success(tmp_path: Path) -> None:
    model = tmp_path / "base.wdi"
    model.write_bytes(b"x")
    binp = tmp_path / "bin"
    binp.mkdir()
    cfg = make_config(
        model={
            "model_path": str(model),
            "wanda_bin": str(binp),
            "base_model_name": "base",
        },
        output_root=str(tmp_path / "runs"),
    )
    validate_optimization_paths(cfg, config_dir=tmp_path)
    assert cfg.model.model_path == model
    assert cfg.output_root == tmp_path / "runs"
