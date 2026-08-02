"""Report configuration schema model."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportConfiguration(BaseModel):
    """Report-oriented descriptive metadata for a scenario."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None)
    appendix: str | None = Field(default=None)
    chapter: int | None = Field(default=None)
    date: Any | None = Field(default=None)

    @field_validator("description", "appendix", mode="before")
    @classmethod
    def nan_to_none_str(cls, v: Any) -> Any:
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

    @field_validator("chapter", mode="before")
    @classmethod
    def nan_to_none_int(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float):
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
        if isinstance(v, float) and math.isnan(v):
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return v
