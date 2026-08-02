"""Post-processing configuration schema models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .plot_route import RoutePlotSpecification
from .report import ReportConfiguration
from .table import MinMaxTableSpecification
from .time_series_plot import TimeSeriesPlotSpecification


class TablePostProcessingConfiguration(BaseModel):
    """Table exports requested for a scenario."""

    model_config = ConfigDict(extra="forbid")

    minmax: list[MinMaxTableSpecification] = Field(default_factory=list)


class FigurePostProcessingConfiguration(BaseModel):
    """Figures requested for a scenario."""

    model_config = ConfigDict(extra="forbid")

    routes: list[RoutePlotSpecification] = Field(default_factory=list)
    time_series: list[TimeSeriesPlotSpecification] = Field(default_factory=list)


class PostProcessingConfiguration(BaseModel):
    """Typed post-processing configuration attached to each scenario."""

    model_config = ConfigDict(extra="forbid")

    tables: TablePostProcessingConfiguration = Field(
        default_factory=TablePostProcessingConfiguration
    )
    figures: FigurePostProcessingConfiguration = Field(
        default_factory=FigurePostProcessingConfiguration
    )
    report: ReportConfiguration = Field(default_factory=ReportConfiguration)
