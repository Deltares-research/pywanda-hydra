"""Top-level scenario specification schema model."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .meta import AnalysisMeta, ScenarioMeta
from .parameter import ChangeMode, ParameterChange
from .post_processing import PostProcessingConfig


class ScenarioSpecification(BaseModel):
    """Data model representing a complete scenario specification."""

    model_config = ConfigDict(extra="forbid")

    meta: ScenarioMeta
    analysis_meta: AnalysisMeta = Field(default_factory=AnalysisMeta)
    parameters: list[ParameterChange] = Field(default_factory=list)
    post_processing: PostProcessingConfig = Field(default_factory=lambda: PostProcessingConfig())
    source: dict[str, Any] = Field(default_factory=dict)

    def iter_parameters(self) -> Iterable[tuple[str, str, Any, ChangeMode]]:
        for p in self.parameters:
            yield p.component, p.property, p.value, p.mode
