"""Parameter change schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from pywandahydra.disuse import parse_disuse_value

from .validators import ensure_non_empty_string

ChangeMode = Literal["set", "scale", "offset"]


class ParameterChange(BaseModel):
    """Data model representing a change to a parameter of a component.

    Attributes:
        component (str): The name of the component whose parameter is to be changed.
        property (str): The name of the parameter to be changed.
        value (Any): The new value for the parameter. If the property is "disuse",
        this value will be parsed into a boolean.
        mode (ChangeMode): The mode of the change, which can be "set", "scale", or "offset".
        Defaults to "set".
    """

    model_config = ConfigDict(extra="forbid")

    component: str
    property: str
    value: Any
    mode: ChangeMode = "set"

    @field_validator("component", "property")
    @classmethod
    def non_empty(cls, v: str, info: Any) -> str:
        field_name = info.field_name or "value"
        return ensure_non_empty_string(v, field_name=field_name)

    @field_validator("value", mode="before")
    @classmethod
    def normalize_disuse_value(cls, v: Any, info: Any) -> bool | Any:
        if info.data.get("property", "").strip().lower() != "disuse" or v is None:
            return v
        return parse_disuse_value(v)
