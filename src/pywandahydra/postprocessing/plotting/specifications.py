"""Object specifications for plotting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScaleType = Literal["linear"]


class AxisSpec(BaseModel):
    """Specification for a plot axis.

    Attributes
    ----------
    label : str
        Label for the axis.
    min : Optional[float]
        Minimum limit for the axis.
    max : Optional[float]
        Maximum limit for the axis.
    tick_interval : Optional[float]
        Interval between ticks on the axis.
    scale : ScaleType
        Scaling type for the axis (e.g., "linear").
    factor : float
        Scaling factor for the axis.
    """

    model_config = ConfigDict(extra="forbid")

    label: str | None = None

    # Axis limits
    min: float | None = None
    max: float | None = None

    # Tick spacing
    tick_interval: float | None = None

    # Scaling of the axis
    scale: ScaleType = "linear"  # or "log"
    factor: float = Field(default=1.0, gt=0.0, description="Scaling factor for the axis.")

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()
