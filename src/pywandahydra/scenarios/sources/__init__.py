"""Scenario sources package.

Registers all built-in source backends on import.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from .base import (  # noqa: F401
    ScenarioSource,
    get_source_for_extension,
    list_source_classes,
    list_source_extensions,
    register_source,
)
from .xls import XlsScenarioSource

logger = logging.getLogger(__name__)


def bootstrap() -> None:
    """Register built-in and entry-point scenario sources."""
    register_source(XlsScenarioSource)
    for ep in entry_points(group="pywandahydra.scenario_sources"):
        try:
            register_source(ep.load())
        except Exception:
            logger.exception(
                "Failed to load pywandahydra.scenario_sources plugin %r", ep.name
            )


bootstrap()
