"""Scenario sources package.

Registers all built-in source backends on import.
"""

from .base import ScenarioSource, get_source_for_extension, register_source  # noqa: F401
from .xls_source import XlsScenarioSource  # noqa: F401
