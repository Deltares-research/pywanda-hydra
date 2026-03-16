"""Object specifications for plotting."""

from __future__ import annotations

from typing import Literal, Optional

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

    label: str = None

    # Axis limits
    min: Optional[float] = None
    max: Optional[float] = None

    # Tick spacing
    tick_interval: Optional[float] = None

    # Scaling of the axis
    scale: ScaleType = "linear"  # or "log"
    factor: float = Field(default=1.0, gt=0.0, description="Scaling factor for the axis.")

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        return (v or "").strip()
