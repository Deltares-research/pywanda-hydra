"""Compatibility facade for scenario schema models.

This module re-exports the canonical models from ``pywandahydra.scenarios.models``
to preserve the long-standing import path ``pywandahydra.scenarios.schema``.
"""

from __future__ import annotations

from .models import (
    AnalysisMeta,
    AxisSpecification,
    ChangeMode,
    ExportTableSpecification,
    ParameterChange,
    PlotTextAnnotation,
    PostProcessingConfig,
    RoutePlotSpecification,
    ScenarioDocument,
    ScenarioMeta,
    ScenarioSpecification,
    ScenarioWarning,
    TimePlotSpecification,
)

__all__ = [
    "AnalysisMeta",
    "AxisSpecification",
    "ChangeMode",
    "ExportTableSpecification",
    "ParameterChange",
    "PlotTextAnnotation",
    "PostProcessingConfig",
    "RoutePlotSpecification",
    "ScenarioDocument",
    "ScenarioMeta",
    "ScenarioSpecification",
    "ScenarioWarning",
    "TimePlotSpecification",
]
