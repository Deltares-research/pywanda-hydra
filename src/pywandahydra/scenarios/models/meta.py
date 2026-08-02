"""Analysis-level metadata schema model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AnalysisMeta(BaseModel):
    """Data model representing global analysis metadata."""

    model_config = ConfigDict(extra="allow")

    analysis_description: str | None = None
    wanda_version: str | None = None
    project_number: int | None = None

    @field_validator("analysis_description", "wanda_version", mode="before")
    @classmethod
    def normalize_str(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("project_number", mode="before")
    @classmethod
    def coerce_project_number(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return v
