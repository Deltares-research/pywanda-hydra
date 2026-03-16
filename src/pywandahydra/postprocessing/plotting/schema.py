"""Object schemas for plotting specifications in post-processing."""

from __future__ import annotations

from typing import List, Literal, Optional

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
    values: List[float]  # same length as RouteData.s_location


class RouteData(BaseModel):
    """Specification for route plot data."""

    model_config = ConfigDict(extra="forbid")

    s_location: List[float]
    series: List[RouteSeries]

    s_location_profile: Optional[List[float]] = None
    elevation: Optional[List[float]] = None

    start_label: Optional[str] = None
    end_label: Optional[str] = None

    text_annotations: List[PlotTextAnnotation] = Field(default_factory=list)
