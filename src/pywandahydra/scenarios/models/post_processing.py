"""Post-processing configuration schema model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .plot_route import RoutePlotSpecification
from .plot_time import TimePlotSpecification
from .tables import ExportTableSpecification


class PostProcessingConfig(BaseModel):
    """Typed post-processing configuration attached to each scenario."""

    model_config = ConfigDict(extra="forbid")

    tables: list[ExportTableSpecification] = Field(default_factory=list)
    routes: list[RoutePlotSpecification] = Field(default_factory=list)
    time_plots: list[TimePlotSpecification] = Field(default_factory=list)
    enabled_steps: list[str] = Field(default_factory=list)
    theme: str = "default"
