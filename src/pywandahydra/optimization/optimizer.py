"""Outer optimization loop over surge-vessel counts.

For each candidate number of surge vessels the optimizer runs two bisection
searches — one for the minimum-pressure criterion (at the pressure Laplace
coefficient) and one for the minimum-water-level criterion (at the water-level
Laplace coefficient) — and combines the resulting bounds into the feasible
C-value range. The smallest vessel count with a non-empty range is the optimum.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from multiprocessing import get_context

from .bisection import BisectionResult, find_boundary
from .config import OptimizationConfig
from .evaluator import EvaluationResult, Evaluator
from .results import CriterionBoundary, OptimizationResults, VesselResult

logger = logging.getLogger(__name__)


def _to_boundary(criterion: str, laplace: float, result: BisectionResult) -> CriterionBoundary:
    return CriterionBoundary(
        criterion=criterion,
        laplace=laplace,
        boundary=result.boundary,
        bound_type=result.bound_type,
        converged=result.converged,
        iterations=result.iterations,
    )


def _combine(
    config: OptimizationConfig,
    pressure: BisectionResult,
    water_level: BisectionResult,
) -> tuple[float | None, float | None, bool]:
    """Intersect the two criteria into a feasible C-range.

    Returns ``(c_lower, c_upper, feasible)``.
    """
    lower_bounds = [config.c_value.lower]
    upper_bounds = [config.c_value.upper]
    infeasible = False

    for result in (pressure, water_level):
        if result.bound_type == "lower" and result.boundary is not None:
            lower_bounds.append(result.boundary)
        elif result.bound_type == "upper" and result.boundary is not None:
            upper_bounds.append(result.boundary)
        elif result.bound_type == "none_acceptable":
            infeasible = True

    c_lower = max(lower_bounds)
    c_upper = min(upper_bounds)
    feasible = (not infeasible) and c_lower <= c_upper
    if not feasible:
        return c_lower, c_upper, False
    return c_lower, c_upper, True


def _optimize_vessel(
    config: OptimizationConfig, evaluator: Evaluator, n: int
) -> VesselResult:
    """Run both criterion bisections for a single surge-vessel count.

    This is a module-level function (rather than a closure) so it is picklable
    and can be dispatched to a spawned worker process.

    Args:
        config: The validated optimization configuration.
        evaluator: Evaluator mapping ``(n, C, laplace)`` triples to metrics.
        n: The number of surge vessels to evaluate.

    Returns:
        The :class:`VesselResult` for this vessel count.
    """
    logger.info("Optimizing for %d surge vessel(s)", n)

    memo: dict[tuple[int, float, float], EvaluationResult] = {}

    def evaluate(c_value: float, laplace: float) -> EvaluationResult:
        key = (n, c_value, laplace)
        if key not in memo:
            memo[key] = evaluator.run(n, c_value, laplace)
        return memo[key]

    def pressure_ok(c: float) -> bool:
        metrics = evaluate(c, config.laplace.pressure)
        return metrics.min_pressure >= config.acceptance.min_pressure

    def water_level_ok(c: float) -> bool:
        metrics = evaluate(c, config.laplace.water_level)
        return metrics.min_water_level >= config.acceptance.min_water_level

    lower = config.c_value.lower
    upper = config.c_value.upper
    rel_tol = config.convergence.rel_tol
    max_iter = config.convergence.max_iter

    pressure_res = find_boundary(pressure_ok, lower, upper, rel_tol=rel_tol, max_iter=max_iter)
    water_level_res = find_boundary(
        water_level_ok, lower, upper, rel_tol=rel_tol, max_iter=max_iter
    )

    c_lower, c_upper, feasible = _combine(config, pressure_res, water_level_res)
    return VesselResult(
        n_vessels=n,
        pressure=_to_boundary("pressure", config.laplace.pressure, pressure_res),
        water_level=_to_boundary("water_level", config.laplace.water_level, water_level_res),
        c_lower=c_lower,
        c_upper=c_upper,
        feasible=feasible,
    )


def _parallel_map(
    func: Callable[[OptimizationConfig, Evaluator, int], VesselResult],
    config: OptimizationConfig,
    evaluator: Evaluator,
    counts: list[int],
    n_workers: int,
) -> list[VesselResult]:
    """Map ``func`` over ``counts`` in parallel, preserving input order.

    Uses a ``spawn`` process pool (matching the batch runner). The number of
    worker processes is capped at the number of vessel counts.
    """
    processes = min(n_workers, len(counts))
    logger.info("Running %d vessel counts across %d worker process(es)", len(counts), processes)
    mp = get_context("spawn")
    with mp.Pool(processes=processes) as pool:
        return pool.starmap(func, [(config, evaluator, n) for n in counts])


def optimize(config: OptimizationConfig, evaluator: Evaluator) -> OptimizationResults:
    """Run the surge-vessel optimization.

    Vessel counts are independent and are optimized in parallel when
    ``config.n_workers > 1``; otherwise they run sequentially.

    Args:
        config: The validated optimization configuration.
        evaluator: Evaluator mapping ``(n, C, laplace)`` triples to metrics.

    Returns:
        Aggregated :class:`OptimizationResults`.
    """
    counts = config.number_of_vessels.values()

    if config.n_workers > 1 and len(counts) > 1:
        vessels = _parallel_map(_optimize_vessel, config, evaluator, counts, config.n_workers)
    else:
        vessels = [_optimize_vessel(config, evaluator, n) for n in counts]

    min_feasible = next((v.n_vessels for v in vessels if v.feasible), None)
    if min_feasible is None:
        logger.warning("No feasible surge-vessel count found within the given bounds.")
    else:
        logger.info("Minimum feasible number of surge vessels: %d", min_feasible)

    return OptimizationResults(
        run_id=config.run_id,
        vessels=vessels,
        min_feasible_vessels=min_feasible,
    )
