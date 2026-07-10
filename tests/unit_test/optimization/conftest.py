"""Shared fixtures for optimization tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pywandahydra.optimization.config import OptimizationConfig
from pywandahydra.optimization.evaluator import EvaluationResult


@dataclass
class SyntheticEvaluator:
    """Deterministic WANDA-free evaluator for optimizer tests.

    Encodes two crossing acceptance thresholds so that:

    * the pressure criterion imposes a **lower** C bound at ``20 - n``;
    * the water-level criterion imposes an **upper** C bound at ``5 + n``.

    The range is feasible only when ``20 - n <= 5 + n`` (i.e. ``n >= 8``).
    """

    calls: int = 0

    def run(self, n_vessels: int, c_value: float, laplace: float) -> EvaluationResult:
        self.calls += 1
        min_pressure = c_value - (20 - n_vessels)
        min_water_level = (5 + n_vessels) - c_value
        return EvaluationResult(
            n_vessels=n_vessels,
            c_value=c_value,
            laplace=laplace,
            min_pressure=min_pressure,
            min_water_level=min_water_level,
        )


def make_config(**overrides: object) -> OptimizationConfig:
    """Build a minimal valid OptimizationConfig for tests."""
    data: dict = {
        "run_id": "test_opt",
        "output_root": "./runs",
        "model": {
            "model_path": "./base.wdi",
            "wanda_bin": "./bin",
            "base_model_name": "base",
        },
        "surge_vessel": "SURGE",
        "pressure_pipes_keyword": "PIPE",
        "acceptance": {"min_pressure": 0.0, "min_water_level": 0.0},
        "number_of_vessels": {"min": 1, "max": 10, "step": 1},
        "c_value": {"lower": 1.0, "upper": 30.0},
        "convergence": {"rel_tol": 0.001, "max_iter": 40},
    }
    data.update(overrides)
    return OptimizationConfig.model_validate(data)


@pytest.fixture
def config() -> OptimizationConfig:
    return make_config()


@pytest.fixture
def synthetic_evaluator() -> SyntheticEvaluator:
    return SyntheticEvaluator()
