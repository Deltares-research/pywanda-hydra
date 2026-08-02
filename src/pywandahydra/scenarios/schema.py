"""Compatibility facade for scenario schema models.

This module re-exports the canonical models from ``pywandahydra.scenarios.models``
to preserve the long-standing import path ``pywandahydra.scenarios.schema``.
"""

from __future__ import annotations

from .models import (
    AnalysisMeta,
    AxisSpecification,
    FigurePostProcessingConfiguration,
    MinMaxTableSpecification,
    ModelParameterChange,
    PlotTextAnnotation,
    PostProcessingConfiguration,
    ReportConfiguration,
    RoutePlotSpecification,
    ScenarioDocument,
    ScenarioSpecification,
    ScenarioWarning,
    TablePostProcessingConfiguration,
    TimeSeriesPlotSpecification,
)

__all__ = [
    "AnalysisMeta",
    "AxisSpecification",
    "FigurePostProcessingConfiguration",
    "MinMaxTableSpecification",
    "ModelParameterChange",
    "PlotTextAnnotation",
    "PostProcessingConfiguration",
    "ReportConfiguration",
    "RoutePlotSpecification",
    "ScenarioDocument",
    "ScenarioSpecification",
    "ScenarioWarning",
    "TablePostProcessingConfiguration",
    "TimeSeriesPlotSpecification",
]
