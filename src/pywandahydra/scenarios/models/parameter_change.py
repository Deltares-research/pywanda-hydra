"""Model parameter change schema model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .validators import ensure_non_empty_string


class ModelParameterChange(BaseModel):
    """A change applied to a single property of a WANDA model component.

    Attributes:
        component (str): The name of the component whose property is changed.
        property (str): The name of the property to change.
        value (Any): The authored value for the property, kept raw. Any
            WANDA-specific interpretation (such as ``disuse`` semantics) is
            applied at the WANDA boundary, not on this model.
    """

    model_config = ConfigDict(extra="forbid")

    component: str
    property: str
    value: Any

    @field_validator("component", "property")
    @classmethod
    def non_empty(cls, v: str, info: Any) -> str:
        field_name = info.field_name or "value"
        return ensure_non_empty_string(v, field_name=field_name)
