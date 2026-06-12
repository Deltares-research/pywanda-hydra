"""Data models for scenario specifications using Pydantic."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pywandahydra.disuse import parse_disuse_value
from pywandahydra.postprocessing.plotting.specifications import AxisSpec

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

        Disused: 0, 0.0, "0", "yes", "true", "y", "disuse"
        In use:  1, 1.0, "1", "no", "false", "n", "use"

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

        return parse_disuse_value(v)


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
    description: str | None = Field(None, alias="Description")
    extra: str | None = Field(None, alias="Extra")
    appendix: str | None = Field(None, alias="Appendix")
    chapter: int | None = Field(None, alias="Chapter")
    date: Any | None = Field(None, alias="Date")

    @field_validator("description", "extra", "appendix", mode="before")
    @classmethod
    def nan_to_none_str(cls, v: Any) -> Any:
        """Convert NaN float values to None for optional string fields.

        Parameters
        ----------
        v : Any
            The input value.

        Returns
        -------
        Any
            None if the value is NaN, else the original value.
        """
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
        return v

    @field_validator("chapter", mode="before")
    @classmethod
    def nan_to_none_int(cls, v: Any) -> Any:
        """Convert NaN float values to None for optional int fields.

        Parameters
        ----------
        v : Any
            The input value.

        Returns
        -------
        Any
            None if NaN, coerced int if whole float, else original.
        """
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
        """Convert datetime objects to ISO format strings for JSON serialization.

        Parameters
        ----------
        v : Any
            The input date value.

        Returns
        -------
        Any
            The date as a string (if datetime) or the original value.
        """
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
        """Coerce various input types to a boolean for the "include" field.

        Parameters
        ----------
        v : Any
            The input value to validate.

        Returns
        -------
        bool: The coerced boolean value.
        """
        if v is None:
            return True  # Default to included
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return True  # NaN treated as default (included)
            return bool(int(v) == 1)
        if isinstance(v, int):
            return bool(v == 1)
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

    analysis_description: str | None = None
    wanda_version: str | None = None
    project_number: int | None = None

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
    parameters: list[ParameterChange] = Field(default_factory=list)

    # Post-processing configuration (tables, routes, enabled steps)
    post_processing: PostProcessingConfig = Field(
        default_factory=lambda: PostProcessingConfig()
    )

    # Provenance, traceability, and source-specific context
    source: dict[str, Any] = Field(default_factory=dict)

    def iter_parameters(self) -> Iterable[tuple[str, str, Any, ChangeMode]]:
        """Convenience iterator for execution layer."""
        for p in self.parameters:
            yield p.component, p.property, p.value, p.mode


class ExportTableSpecification(BaseModel):
    """Data model representing specifications for exporting a table.

    Attributes
    ----------
    component : str
        The name of the component to export.
    property : str
        The name of the property to export.
    mode : str
        The mode of the table export: ``"MIN"`` or ``"MAX"``.
    """

    model_config = ConfigDict(extra="forbid")

    component: str
    property: str
    mode: Literal["MIN", "MAX"]

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

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate that the mode is either "MIN" or "MAX".

        Parameters
        ----------
        v : str
            The input mode string to validate.

        Returns
        -------
        str: The validated mode string.
        """
        v = str(v).strip().upper()
        if v not in ("MIN", "MAX"):
            raise ValueError("mode must be either 'MIN' or 'MAX'")
        return v


class RoutePlotSpecification(BaseModel):
    """Data model representing a route-plot specification loaded from a scenario file.

    Attributes
    ----------
    component : str
        The name of the component to plot.
    route_id : str
        The ID of the route to plot.
    title : Optional[str]
        Plot title.
    legend : Optional[str]
        Legend label or description.
    x_axis : AxisSpec
        X-axis specification (label, limits, tick interval, scale factor).
    y_axis : AxisSpec
        Y-axis specification (label, limits, tick interval, scale factor).
    """

    model_config = ConfigDict(extra="forbid")

    route_id: str
    property: str

    title: str | None = None
    legend: str | None = None
    # Optional report-page grouping metadata from RPlots (legacy-compatible).
    fig: str | None = None
    plot: int | None = None
    x_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))
    y_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))

    @field_validator("title")
    @classmethod
    def non_empty(cls, v: str) -> str:
        """Ensure the string is non-empty after stripping whitespace."""
        v = str(v).strip()
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("fig", mode="before")
    @classmethod
    def normalize_fig(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
            if v.is_integer():
                return str(int(v))
        s = str(v).strip()
        return s or None

    @field_validator("plot", mode="before")
    @classmethod
    def normalize_plot(cls, v: Any) -> int | None:
        if v is None:
            return None
        if isinstance(v, float):
            import math

            if math.isnan(v):
                return None
            if v.is_integer():
                return int(v)
            raise ValueError("plot must be an integer")
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if s.isdigit():
                return int(s)
            raise ValueError("plot must be an integer")
        if isinstance(v, int):
            return v
        return None


class PostProcessingConfig(BaseModel):
    """Typed post-processing configuration attached to each scenario.

    Groups all post-processing inputs (table exports, route plots), the
    optional allow-list of step names to run, and plot theme selection.
    An empty ``enabled_steps`` means "run every applicable registered step".
    """

    model_config = ConfigDict(extra="forbid")

    tables: list[ExportTableSpecification] = Field(default_factory=list)
    routes: list[RoutePlotSpecification] = Field(default_factory=list)
    # Allow-list of post-processing step names; empty = all applicable steps.
    enabled_steps: list[str] = Field(default_factory=list)
    # Plot theme name (e.g., 'default', 'deltares_light'). Defaults to 'default'.
    theme: str = "default"


# Resolve the forward reference used on ScenarioSpecification.post_processing.
ScenarioSpecification.model_rebuild()
