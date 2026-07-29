"""Scenario sources package.

Registers all built-in source backends on import.
"""

from __future__ import annotations

import logging

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
    """Register built-in scenario sources.

    External extension machinery has been removed; only built-in sources
    are available.
    """
    register_source(XlsScenarioSource)


bootstrap()
