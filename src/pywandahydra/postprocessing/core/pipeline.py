"""Post-processing pipeline — pluggable steps that run after simulation.

Each post-processor is a submodule implementing case/run step protocols.
The pipeline resolves a workflow and executes its case-level steps.

Adding a new step:
    1. Create a module under ``postprocessing/steps/``
    2. Implement a class satisfying the case-step protocol
    3. Add it to a workflow implementation

Each step receives a :class:`CaseContext` with everything it needs
(cache, scenario spec, case directory, export config).
"""

from __future__ import annotations

import logging
from typing import Any

from .context import CaseContext

logger = logging.getLogger(__name__)


def run_postprocessing(
    ctx: CaseContext,
    *,
    workflow_name: str,
    workflow_params: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """Run post-processing steps for a single case.

    Args:
        ctx: The post-processing context for a single case.
        workflow_name: Workflow name used to resolve ordered step instances.
        workflow_params: Optional parameter dict passed to workflow ``Params``.

    Returns:
        Dict mapping step name → success (True/False).
    """
    from ..workflows.base import resolve_workflow

    workflow = resolve_workflow(workflow_name, workflow_params)
    steps = workflow.case_steps(ctx)

    results: dict[str, bool] = {}

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
