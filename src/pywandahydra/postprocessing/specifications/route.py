"""Declarative specifications for route plots in post-processing."""

from __future__ import annotations

from typing import List, Union

from pydantic import BaseModel, ConfigDict, Field

from pywandahydra.postprocessing.plotting.specifications import AxisSpec

from .base import PlotSpecification


class RoutePlotSpec(PlotSpecification):
    """
    Declarative specification for a route plot.
    """

    model_config = ConfigDict(extra="forbid")

    route_identifier: str  # keyword or explicit route name
    property: str
    times: List[Union[float, str]] = Field(default_factory=list)

    plot_elevation: bool = False

    x_axis: AxisSpec
    y_axis: AxisSpec
