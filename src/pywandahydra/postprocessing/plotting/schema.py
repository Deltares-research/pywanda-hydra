"""Object schemas for plotting specifications in post-processing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScaleType = Literal["linear"]


class PlotTextAnnotation(BaseModel):
    """Specification for a text annotation on a plot."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    dx: float = 0.0
    dy: float = 0.0
    text: str


class RouteSeries(BaseModel):
    """Specification for a data series in a route plot."""

    model_config = ConfigDict(extra="forbid")

    label: str  # e.g. "0 s", "60 s", "min", "max"
    values: list[float]  # same length as RouteData.s_location


class RouteData(BaseModel):
    """Specification for route plot data."""

    model_config = ConfigDict(extra="forbid")

    s_location: list[float]
    series: list[RouteSeries]

    s_location_profile: list[float] | None = None
    elevation: list[float] | None = None

    start_label: str | None = None
    end_label: str | None = None

    text_annotations: list[PlotTextAnnotation] = Field(default_factory=list)
