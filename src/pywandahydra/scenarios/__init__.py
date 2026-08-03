"""Curated public API for scenario loading and models."""

from .excel.validation import ScenarioValidationError
from .loader import (
    ScenarioLoadOptions,
    assert_scenario_file_valid,
    check_scenario_file,
    load_scenario_document,
    load_scenarios,
)
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
    "ScenarioLoadOptions",
    "ScenarioSpecification",
    "ScenarioValidationError",
    "ScenarioWarning",
    "TablePostProcessingConfiguration",
    "TimeSeriesPlotSpecification",
    "assert_scenario_file_valid",
    "check_scenario_file",
    "load_scenario_document",
    "load_scenarios",
]
