"""Axis and annotation models used by scenario plot specifications."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScaleType = Literal["linear"]


class AxisSpecification(BaseModel):
    """Specification for a plot axis."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    min: float | None = None
    max: float | None = None
    tick_interval: float | None = None
    scale: ScaleType = "linear"
    factor: float = Field(default=1.0, gt=0.0, description="Scaling factor for the axis.")

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()


class PlotTextAnnotation(BaseModel):
    """Specification for a text annotation on a plot."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    dx: float = 0.0
    dy: float = 0.0
    text: str
