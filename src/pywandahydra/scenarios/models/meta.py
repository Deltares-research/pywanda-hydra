"""Scenario metadata schema models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioMeta(BaseModel):
    """Data model representing metadata for a scenario."""

    model_config = ConfigDict(extra="allow")

    number: int = Field(..., alias="Number")
    include: bool = Field(True, alias="Include")
    name: str = Field(..., alias="Name")

    description: str | None = Field(None, alias="Description")
    extra: str | None = Field(None, alias="Extra")
    appendix: str | None = Field(None, alias="Appendix")
    chapter: int | None = Field(None, alias="Chapter")
    date: Any | None = Field(None, alias="Date")

    @field_validator("description", "extra", "appendix", mode="before")
    @classmethod
    def nan_to_none_str(cls, v: Any) -> Any:
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
        return v

    @field_validator("chapter", mode="before")
    @classmethod
    def nan_to_none_int(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
            if v.is_integer():
                return int(v)
        return v

    @field_validator("date", mode="before")
    @classmethod
    def normalize_date(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name must be non-empty")
        return s

    @field_validator("number", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> Any:
        if v is None:
            return v
        if isinstance(v, float):
            import math

            if math.isnan(v):
                raise ValueError("Number must not be NaN")
            if v.is_integer():
                return int(v)
        return v

    @field_validator("include", mode="before")
    @classmethod
    def coerce_include(cls, v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return True
            return bool(int(v) == 1)
        if isinstance(v, int):
            return bool(v == 1)
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "y")
        return bool(v)


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
