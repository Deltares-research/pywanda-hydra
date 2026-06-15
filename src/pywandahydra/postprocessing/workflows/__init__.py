"""Post-processing workflows — pluggable analysis strategies.

A workflow defines *which* post-processing steps to run and in what
order for a given case.

Usage:
    1. Create a class implementing the :class:`PostProcessingWorkflow` protocol.
    2. Register it with :func:`register_workflow`.
    3. Reference it by name in the run config.

Built-in workflows are registered via :func:`bootstrap`, which must
be called once per process (idempotent, safe to call repeatedly).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

from ..steps.aggregate_tables import AggregateTablesStep
from ..steps.merge_pdfs import MergePdfsStep
from ..steps.plot_report import PlotReportStep
from ..steps.summary_table import SummaryTableStep
from .base import (
    build_case_step,
    build_run_step,
    get_case_step_class,
    get_run_step_class,
    get_workflow_class,
    list_case_steps,
    list_run_steps,
    list_workflows,
    register_case_step,
    register_run_step,
    register_workflow,
    resolve_workflow,
)
from .composed import ConfigDrivenWorkflow
from .default import DefaultWorkflow

logger = logging.getLogger(__name__)


def _load_group(group: str, register: Callable[[type[Any]], type[Any]]) -> None:
    """Load plugin classes from an entry-point group."""
    for ep in entry_points(group=group):
        try:
            register(ep.load())
        except Exception:
            logger.exception("Failed to load %s plugin %r", group, ep.name)


def bootstrap() -> None:
    """Register all built-in workflows.

    Idempotent: safe to call from every worker process under multiprocessing
    ``spawn`` start method, and safe to call multiple times in the same
    process. Tests can call this to ensure a clean registration state.
    """
    register_case_step(SummaryTableStep)
    register_case_step(PlotReportStep)
    register_run_step(AggregateTablesStep)
    register_run_step(MergePdfsStep)
    register_workflow(DefaultWorkflow)
    register_workflow(ConfigDrivenWorkflow)
    _load_group("pywandahydra.case_steps", register_case_step)
    _load_group("pywandahydra.run_steps", register_run_step)
    _load_group("pywandahydra.workflows", register_workflow)


__all__ = [
    "ConfigDrivenWorkflow",
    "DefaultWorkflow",
    "build_case_step",
    "build_run_step",
    "bootstrap",
    "get_case_step_class",
    "get_workflow_class",
    "get_run_step_class",
    "list_case_steps",
    "list_workflows",
    "list_run_steps",
    "register_case_step",
    "register_workflow",
    "register_run_step",
    "resolve_workflow",
]
