"""Top-level scenario specification schema model."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .parameter_change import ModelParameterChange
from .post_processing import PostProcessingConfiguration


class ScenarioSpecification(BaseModel):
    """A single scenario: flat identity, parameter changes, and post-processing."""

    model_config = ConfigDict(extra="forbid")

    number: int
    include: bool = True
    name: str

    parameter_changes: list[ModelParameterChange] = Field(default_factory=list)
    post_processing: PostProcessingConfiguration = Field(
        default_factory=PostProcessingConfiguration
    )
    extra_columns: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)

    @field_validator("number", mode="before")
    @classmethod
    def coerce_number(cls, v: Any) -> Any:
        if isinstance(v, float):
            if math.isnan(v):
                raise ValueError("number must not be NaN")
            if v.is_integer():
                return int(v)
        return v

    @field_validator("include", mode="before")
    @classmethod
    def coerce_include(cls, v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, float):
            if math.isnan(v):
                return True
            return int(v) == 1
        if isinstance(v, int):
            return v == 1
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "y")
        return bool(v)

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must be non-empty")
        return s
