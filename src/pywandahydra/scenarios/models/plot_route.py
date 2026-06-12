"""Route-plot schema model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pywandahydra.postprocessing.plotting.models import AxisSpec

from .validators import (
    ensure_non_empty_string,
    normalize_fig,
    normalize_optional_int,
)


class RoutePlotSpecification(BaseModel):
    """Data model representing a route-plot specification loaded from a scenario file."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    property: str

    title: str | None = None
    legend: str | None = None
    fig: str | None = None
    plot: int | None = None
    x_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))
    y_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))

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
