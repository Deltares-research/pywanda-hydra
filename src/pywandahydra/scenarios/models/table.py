"""Min/max post-processing table schema model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from .validators import ensure_non_empty_string


class MinMaxTableSpecification(BaseModel):
    """A request to export the minimum or maximum of a component property."""

    model_config = ConfigDict(extra="forbid")

    component: str
    property: str
    mode: Literal["MIN", "MAX"]

    @field_validator("component", "property")
    @classmethod
    def non_empty(cls, v: str, info: object) -> str:
        field_name = getattr(info, "field_name", None) or "value"
        return ensure_non_empty_string(v, field_name=field_name)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        s = str(v).strip().upper()
        if s not in ("MIN", "MAX"):
            raise ValueError("mode must be either 'MIN' or 'MAX'")
        return s
