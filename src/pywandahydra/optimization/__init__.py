"""Surge-vessel optimization (Zwan et al. 2012).

Reproduces the surge-vessel optimization routine from
*van der Zwan et al. 2012 — "Optimization of surge protection for a large water
transmission scheme in Abu Dhabi"*.

For a WANDA model containing an inclined surge vessel, the routine determines the
acceptable range of C-values (``C = p * V``, mass control) for a varying number of
surge vessels, using a bisection search against two acceptance criteria:

* minimum pipeline pressure (evaluated at Laplace coefficient 1.4), and
* minimum surge-vessel water level (evaluated at Laplace coefficient 1.0).
"""

from __future__ import annotations

from .bisection import BisectionResult, find_boundary
from .config import OptimizationConfig, load_optimization_config, validate_optimization_paths
from .evaluator import EvaluationResult, Evaluator, WandaEvaluator, build_scenario
from .optimizer import VesselResult, optimize
from .results import OptimizationResults, write_csv, write_json
from .runner import run_optimization

__all__ = [
    "BisectionResult",
    "EvaluationResult",
    "Evaluator",
    "OptimizationConfig",
    "OptimizationResults",
    "VesselResult",
    "WandaEvaluator",
    "build_scenario",
    "find_boundary",
    "load_optimization_config",
    "optimize",
    "run_optimization",
    "validate_optimization_paths",
    "write_csv",
    "write_json",
]
