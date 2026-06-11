"""Post-processing methodologies — pluggable analysis strategies.

A methodology defines *which* post-processing steps to run and in what
order for a given case.

Usage:
    1. Create a class implementing the :class:`Methodology` protocol.
    2. Register it with :func:`register_methodology`.
    3. Reference it by name in the run config.

Built-in methodologies are registered via :func:`bootstrap`, which must
be called once per process (idempotent, safe to call repeatedly).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

from ..steps.aggregate_tables import AggregateTablesStep
from ..steps.merge_pdfs import MergePdfsStep
from ..steps.route_plots import RoutePlotStep
from ..steps.summary_table import SummaryTableStep
from .base import (
    build_case_step,
    build_run_step,
    get_case_step_class,
    get_methodology_class,
    get_run_step_class,
    list_case_steps,
    list_methodologies,
    list_run_steps,
    register_case_step,
    register_methodology,
    register_run_step,
    resolve_methodology,
)
from .composed import ComposedMethodology
from .default import DefaultMethodology

logger = logging.getLogger(__name__)


def _load_group(group: str, register: Callable[[type[Any]], type[Any]]) -> None:
    """Load plugin classes from an entry-point group."""
    for ep in entry_points(group=group):
        try:
            register(ep.load())
        except Exception:
            logger.exception("Failed to load %s plugin %r", group, ep.name)


def bootstrap() -> None:
    """Register all built-in methodologies.

    Idempotent: safe to call from every worker process under multiprocessing
    ``spawn`` start method, and safe to call multiple times in the same
    process. Tests can call this to ensure a clean registration state.
    """
    register_case_step(SummaryTableStep)
    register_case_step(RoutePlotStep)
    register_run_step(AggregateTablesStep)
    register_run_step(MergePdfsStep)
    register_methodology(DefaultMethodology)
    register_methodology(ComposedMethodology)
    _load_group("pywandahydra.case_steps", register_case_step)
    _load_group("pywandahydra.run_steps", register_run_step)
    _load_group("pywandahydra.methodologies", register_methodology)


__all__ = [
    "ComposedMethodology",
    "DefaultMethodology",
    "build_case_step",
    "build_run_step",
    "bootstrap",
    "get_case_step_class",
    "get_methodology_class",
    "get_run_step_class",
    "list_case_steps",
    "list_methodologies",
    "list_run_steps",
    "register_case_step",
    "register_methodology",
    "register_run_step",
    "resolve_methodology",
]
