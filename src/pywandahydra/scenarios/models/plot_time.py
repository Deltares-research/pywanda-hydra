"""Time-plot schema model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pywandahydra.postprocessing.plotting.models import AxisSpec

from .validators import (
    ensure_non_empty_string,
    normalize_fig,
    normalize_optional_float,
    normalize_optional_int,
)


class TimePlotSpecification(BaseModel):
    """Data model representing a time-plot specification loaded from a scenario file.

    Attributes:
        component (str): The name of the component to plot.
        property (str): The name of the property to plot.
        title (str | None): The title of the plot.
        legend (str | None): The legend label for the plot.
        fig (str | None): The figure identifier for the plot.
        plot (int | None): The plot number within the figure.
        location (float | None): For pipes, the location (s-distance) at which the
            property is plotted.
        color (str | None): The color of the plot line.
        style (str | None): The line style of the plot line.
        marker (str | None): The marker style for the plot line.
        x_axis (AxisSpec): The specification for the x-axis.
        y_axis (AxisSpec): The specification for the y-axis.

    """

    model_config = ConfigDict(extra="forbid")

    component: str
    property: str

    title: str | None = None
    legend: str | None = None
    fig: str | None = None
    plot: int | None = None
    location: float | None = None
    color: str | None = None
    style: str | None = None
    marker: str | None = None
    x_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))
    y_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))

    @field_validator("component", "property")
    @classmethod
    def non_empty_component_property(cls, v: str, info: Any) -> str:
        field_name = info.field_name or "value"
        return ensure_non_empty_string(v, field_name=field_name)

    @field_validator("title")
    @classmethod
    def non_empty_title(cls, v: str) -> str:
        return ensure_non_empty_string(v, field_name="title")

    @field_validator("fig", mode="before")
    @classmethod
    def normalize_fig_value(cls, v: Any) -> str | None:
        return normalize_fig(v)

    @field_validator("plot", mode="before")
    @classmethod
    def normalize_plot(cls, v: Any) -> int | None:
        return normalize_optional_int(v, field_name="plot")

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, v: Any) -> float | None:
        return normalize_optional_float(v, field_name="location")
