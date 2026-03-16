"""Schema definitions for post-processing specifications."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PlotKind = Literal["timeseries", "route"]


class PlotSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: PlotKind

    # Items to plot
    series: List[str] = Field(default_factory=list)

    # Plot labels and titles
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None

    # Export options
    to_png: bool = False
    to_pdf: bool = True


class PostProcessingSpecifications(BaseModel):
    """Data model for post-processing specifications.

    Attributes
    ----------
    plots : List[PlotSpec]
        A list of plot specifications.
    """

    model_config = ConfigDict(extra="forbid")

    plots: List[PlotSpec] = Field(
        default_factory=list,
        description="A list of plot specifications.",
    )

    # Options
    options: Dict[str, Any] = Field(
        default_factory=dict,
    )
