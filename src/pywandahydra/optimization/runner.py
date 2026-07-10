"""Top-level entry point for a surge-vessel optimization run."""

from __future__ import annotations

import json
import logging

from ..execution.artifacts import create_run_directories
from .config import OptimizationConfig
from .evaluator import Evaluator, WandaEvaluator
from .optimizer import optimize
from .plotting import plot_acceptable_range
from .results import OptimizationResults, write_csv, write_json

logger = logging.getLogger(__name__)


def run_optimization(
    config: OptimizationConfig,
    *,
    evaluator: Evaluator | None = None,
    c_unit: str = "",
    render_plot: bool = True,
) -> OptimizationResults:
    """Run the full surge-vessel optimization and write outputs.

    Creates the run directory, runs the optimizer, and writes
    ``optimization_results.json``, ``optimization_results.csv`` and (unless
    disabled) the acceptable-C-range plot.

    Args:
        config: The validated optimization configuration.
        evaluator: Evaluator to use; defaults to a :class:`WandaEvaluator`
            driving the real WANDA execution stack.
        c_unit: Optional unit label for the C-value axis in the plot.
        render_plot: Whether to render the acceptable-range plot.

    Returns:
        The aggregated :class:`OptimizationResults`.
    """
    from ..config.models import RunContext

    run_root = config.output_root / config.run_id
    ctx = RunContext(
        run_id=config.run_id,
        timestamp="",
        root_dir=run_root,
        description=config.description,
    )
    create_run_directories(ctx)

    config_dump = run_root / "optimization_config.json"
    config_dump.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    if evaluator is None:
        evaluator = WandaEvaluator(config, run_root)

    results = optimize(config, evaluator)

    write_json(results, run_root / "optimization_results.json")
    write_csv(results, run_root / "optimization_results.csv")

    if render_plot:
        try:
            plot_path = plot_acceptable_range(
                results,
                run_root / "figures" / "acceptable_c_range.png",
                c_unit=c_unit,
            )
            logger.info("Wrote acceptable-range plot to %s", plot_path)
        except Exception:
            logger.exception("Failed to render acceptable-range plot")

    summary = {
        "run_id": results.run_id,
        "min_feasible_vessels": results.min_feasible_vessels,
        "n_vessel_counts": len(results.vessels),
    }
    logger.info("Optimization summary: %s", json.dumps(summary))
    return results
