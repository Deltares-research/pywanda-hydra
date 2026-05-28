"""Post-processing pipeline — pluggable steps that run after simulation.

Each post-processor is a submodule implementing the :class:`PostProcessor`
protocol. The pipeline discovers registered steps and executes them in order.

Adding a new step:
    1. Create a module under ``postprocessing/steps/``
    2. Implement a class satisfying the :class:`PostProcessor` protocol
    3. Register it via :func:`register_step`

Each step receives a :class:`PostProcessingContext` with everything it needs
(cache, scenario spec, case directory, export config).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol, runtime_checkable

from ..scenarios.schema import ScenarioSpecification
from .cache import ParquetCache
from .export import (
    DEFAULT_TABLE_EXPORT_PROPS,
    build_figure_export_props,
)

logger = logging.getLogger(__name__)


@dataclass
class PostProcessingContext:
    """Context object passed to each post-processing step.

    Provides access to cached data, scenario specification, output paths,
    and export configuration.
    """

    cache: ParquetCache
    scenario: ScenarioSpecification
    case_dir: Path
    export_figure_props: Dict[str, Dict[str, Any]] = field(
        default_factory=build_figure_export_props
    )
    export_table_props: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: dict(DEFAULT_TABLE_EXPORT_PROPS)
    )


@runtime_checkable
class PostProcessor(Protocol):
    """Protocol for a post-processing step.

    Each step must declare a ``name`` and implement ``run()``.
    Optionally implement ``applicable()`` to conditionally skip.
    """

    name: str

    def applicable(self, ctx: PostProcessingContext) -> bool:
        """Return True if this step should run for the given context."""
        ...

    def run(self, ctx: PostProcessingContext) -> None:
        """Execute the post-processing step."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_STEPS: List[PostProcessor] = []


def register_step(step: PostProcessor) -> PostProcessor:
    """Register a post-processing step in the pipeline.

    Args:
        step: An instance implementing the PostProcessor protocol.

    Returns:
        The same step (for use as a decorator target on instances).
    """
    _STEPS.append(step)
    logger.debug("Registered post-processing step: %s", step.name)
    return step


def get_steps() -> List[PostProcessor]:
    """Return all registered post-processing steps in order."""
    return list(_STEPS)


def clear_steps() -> None:
    """Remove all registered steps (useful for testing)."""
    _STEPS.clear()


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


def run_postprocessing(
    ctx: PostProcessingContext,
    *,
    methodology: str | None = None,
) -> Dict[str, bool]:
    """Run post-processing steps for a single case.

    When *methodology* is provided, steps are sourced from the named
    methodology plugin. Otherwise falls back to the global step registry
    (legacy behaviour).

    Args:
        ctx: The post-processing context for a single case.
        methodology: Optional methodology name. If None, uses registered steps.

    Returns:
        Dict mapping step name → success (True/False).
    """
    if methodology is not None:
        from .methodologies.base import get_methodology

        meth = get_methodology(methodology)
        steps = meth.get_steps(ctx)
    else:
        steps = list(_STEPS)

    results: Dict[str, bool] = {}

    for step in steps:
        if not step.applicable(ctx):
            logger.debug("Skipping step '%s' (not applicable).", step.name)
            results[step.name] = True
            continue

        try:
            step.run(ctx)
            results[step.name] = True
            logger.info("Post-processing step '%s' completed.", step.name)
        except Exception:
            logger.exception("Post-processing step '%s' failed.", step.name)
            results[step.name] = False

    return results
