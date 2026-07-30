"""Route-plot schema model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .plot_axis import AxisSpecification
from .validators import ensure_non_empty_string, normalize_fig, normalize_optional_int


class RoutePlotSpecification(BaseModel):
    """Data model representing a route-plot specification loaded from a scenario file.

    Attributes:
        route_id (str): The identifier of the route to plot.
        property (str): The name of the property to plot.
        title (str | None): The title of the plot.
        legend (str | None): The legend label for the plot.
        fig (str | None): The figure identifier for the plot.
        plot (int | None): The plot number within the figure.
        x_axis (AxisSpecification): The specification for the x-axis.
        y_axis (AxisSpecification): The specification for the y-axis.
    """

    model_config = ConfigDict(extra="forbid")

    route_id: str
    property: str

    title: str | None = None
    legend: str | None = None
    fig: str | None = None
    plot: int | None = None
    x_axis: AxisSpecification = Field(default_factory=lambda: AxisSpecification(label=""))
    y_axis: AxisSpecification = Field(default_factory=lambda: AxisSpecification(label=""))

    @field_validator("title")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return ensure_non_empty_string(v, field_name="title")

    @field_validator("fig", mode="before")
    @classmethod
    def normalize_fig_value(cls, v: Any) -> str | None:
        return normalize_fig(v)

    @field_validator("plot", mode="before")
    @classmethod
    def normalize_plot(cls, v: Any) -> int | None:
        return normalize_optional_int(v, field_name="plot")
