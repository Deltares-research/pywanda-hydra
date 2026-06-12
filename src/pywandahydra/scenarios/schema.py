"""Compatibility facade for scenario schema models.

This module re-exports the canonical models from ``pywandahydra.scenarios.models``
to preserve the long-standing import path ``pywandahydra.scenarios.schema``.
"""

from __future__ import annotations

from .models import (
    AnalysisMeta,
    ChangeMode,
    ExportTableSpecification,
    ParameterChange,
    PostProcessingConfig,
    RoutePlotSpecification,
    ScenarioMeta,
    ScenarioSpecification,
    TimePlotSpecification,
)

__all__ = [
    "AnalysisMeta",
    "ChangeMode",
    "ExportTableSpecification",
    "ParameterChange",
    "PostProcessingConfig",
    "RoutePlotSpecification",
    "ScenarioMeta",
    "ScenarioSpecification",
    "TimePlotSpecification",
]
