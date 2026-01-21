"""Data models for scenario specifications using Pydantic."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChangeMode = Literal["set", "scale", "offset"]


class ParameterChange(BaseModel):
    """Data model representing a change to a parameter of a component.

    Attributes
    ----------
    component : str
        The name of the component whose parameter is to be changed.
    property : str
        The name of the property to be changed.
    value : Any
        The new value for the property.
    mode : ChangeMode, optional
        The mode of change, which can be "set", "scale", or "offset".
    """

    # Ensure no extra fields are allowed
    model_config = ConfigDict(extra="forbid")

    # Component-property-value triplet
    component: str
    property: str
    value: Any

    # Optional change mode with default "set"
    mode: ChangeMode = "set"
    # unit: Optional[Any] = None

    @field_validator("component", "property")
    @classmethod
    def non_empty(cls, v: str) -> str:
        """Ensure the string is non-empty after stripping whitespace.

        Parameters
        ----------
        v : str
            The input string to validate.

        Returns
        -------
        str: The validated non-empty string.
        """
        v = str(v).strip()
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("value", mode="before")
    @classmethod
    def normalize_disuse_value(cls, v: Any, info: Any) -> bool | Any:
        """Normalize value of 'disuse' property to boolean.

        Inputs:

        Yes: 1, 1.0, "1", "yes", "true", "y", "disuse" (case-insensitive)
        No: 0, 0.0, "0", "no", "false", "n", "use" (case-insensitive)

        Parameters
        ----------
        v : Any
            The input value to validate.
        info : Any
            Additional validation info.

        Returns
        -------
        bool: The normalized boolean value.
        """
        # Check if the property being changed is "disuse"
        if info.data.get("property", "").strip().lower() != "disuse" or v is None:
            return v

        # If already boolean, return as is
        if isinstance(v, bool):
            return v

        # Normalize string inputs
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("1", "yes", "true", "y", "disuse"):
                return True
            elif v_lower in ("0", "no", "false", "n", "use"):
                return False
            else:
                raise ValueError(f"Cannot normalize string '{v}' to boolean for 'disuse' property")

        # Normalize numeric inputs
        if isinstance(v, (int, float)):
            if v == 1 or v == 1.0:
                return True
            elif v == 0 or v == 0.0:
                return False
            else:
                raise ValueError(
                    f"Cannot normalize numeric value '{v}' to boolean for 'disuse' property"
                )

        raise ValueError(
            f"Cannot normalize value of type '{type(v)}' to boolean for 'disuse' property"
        )


class ScenarioMeta(BaseModel):
    """Data model representing metadata for a scenario.

    Attributes
    ----------
    number : int
        The scenario number.
    include : bool
        Whether to include this scenario.
    name : str
        Scenario name.
    description : Optional[str]
        Description of the scenario.
    extra : Optional[str]
        Extra information about the scenario.
    appendix : Optional[str]
        Appendix name (if any) to use in naming of output files.
    chapter : Optional[int]
        Chapter number (if any) to use in naming of output files.
    date : Optional[Any]
        Date associated with the scenario.

    """

    model_config = ConfigDict(extra="allow")

    # Required metadata fields
    number: int = Field(..., alias="Number")
    include: bool = Field(True, alias="Include")
    name: str = Field(..., alias="Name")

    # Optional metadata fields
    description: Optional[str] = Field(None, alias="Description")
    extra: Optional[str] = Field(None, alias="Extra")
    appendix: Optional[str] = Field(None, alias="Appendix")
    chapter: Optional[int] = Field(None, alias="Chapter")
    date: Optional[Any] = Field(None, alias="Date")

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        """Ensure the name is non-empty after stripping whitespace.

        Parameters
        ----------
        v : str
            The input name string to validate.

        Returns
        -------
        str: The validated non-empty name string.
        """
        v = v.strip()
        if not v:
            raise ValueError("Name must be non-empty")
        return v

    @field_validator("number", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> Any:
        """Ensure scenario number is an integer, coercing from float if necessary.

        Parameters
        ----------
        v : Any
            The input value to validate.

        Returns
        -------
        Any: The coerced integer value if applicable, else the original value.
        """
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    @field_validator("include", mode="before")
    @classmethod
    def coerce_include(cls, v: Any) -> bool:
        """Coerce various input types to a boolean for the "include" field.

        Parameters
        ----------
        v : Any
            The input value to validate.

        Returns
        -------
        bool: The coerced boolean value.
        """
        if isinstance(v, (int, float)):
            return bool(int(v) == 1)
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "y")
        return bool(v)


class AnalysisMeta(BaseModel):
    """Data model representing global analysis metadata.

    Attributes
    ----------
    analysis_description : Optional[str]
        Description of the analysis.
    wanda_version : Optional[str]
        Wanda version associated with the analysis.
    project_number : Optional[int]
        Project number associated with the analysis.
    """

    model_config = ConfigDict(extra="allow")

    analysis_description: Optional[str] = None
    wanda_version: Optional[str] = None
    project_number: Optional[int] = None

    @field_validator("analysis_description", "wanda_version", mode="before")
    @classmethod
    def normalize_str(cls, v: Any) -> Any:
        """Normalize string fields by stripping whitespace and converting empty strings to None.

        Parameters
        ----------
        v : Any
            The input value to validate.

        Returns
        -------
        Any: The normalized string or None.
        """
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("project_number", mode="before")
    @classmethod
    def coerce_project_number(cls, v: Any) -> Any:
        """Ensure project number is an integer, coercing from float or string if necessary.

        Parameters
        ----------
        v : Any
            The input value to validate.

        Returns
        -------
        Any: The coerced integer value if applicable, else None.
        """
        if v is None:
            return None
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return v


class ScenarioSpecification(BaseModel):
    """Data model representing a complete scenario specification.

    Attributes
    ----------
    meta : ScenarioMeta
        Metadata for the scenario.
    parameters : List[ParameterChange]
        Parameter changes applied for this scenario.
    source : Dict[str, Any]
        Provenance, traceability, and source-specific context.

    Methods
    -------
    iter_parameters()
        Convenience iterator for execution layer.
    """

    model_config = ConfigDict(extra="forbid")

    # Per-scenario metadata (name, include flag, numbering, etc.)
    meta: ScenarioMeta

    # Analysis-level metadata
    analysis_meta: AnalysisMeta = Field(default_factory=AnalysisMeta)

    # Parameter changes applied for this scenario
    parameters: List[ParameterChange] = Field(default_factory=list)

    # Provenance, traceability, and source-specific context
    source: Dict[str, Any] = Field(default_factory=dict)

    def iter_parameters(self) -> Iterable[tuple[str, str, Any, ChangeMode]]:
        """Convenience iterator for execution layer."""
        for p in self.parameters:
            yield p.component, p.property, p.value, p.mode
