# models/spec.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..scenarios.schema import AnalysisMeta, ParameterChange


class ModelSpecification(BaseModel):
    """Model specification and execution settings.

    Attributes
    ----------
    model_path : str | Path
        Path to .wdi (or base path); internally handled as a string.
    wanda_bin : str | Path
        Path to WANDA binaries and executables; internally handled as a string.
    base_model_name : str
        Name of the base model.

    readonly : bool, optional
        If model output exists, the model is treated as read-only (default is True).

    run_steady : bool, optional
        Whether to run steady simulations (default is True).
    run_unsteady : bool, optional
        Whether to run unsteady simulations (default is False).
    """

    model_config = ConfigDict(extra="forbid")

    model_path: str | Path = Field(..., description="Path to .wdi (or base path)")
    wanda_bin: str | Path = Field(..., description="Path to WANDA binaries and executables")
    base_model_name: str

    # Run settings
    readonly: bool = Field(
        default=True,
        description="If model output exists, the model is treated as read-only.",
    )

    # Optional execution settings you may want centrally:
    run_steady: bool = True
    run_unsteady: bool = False

    # Genneral settings to apply before scenarios (global tweaks)
    global_overrides: list[ParameterChange] = Field(
        default_factory=list,
        description="Global parameter changes to apply before scenarios changes.",
    )

    @field_validator("model_path")
    @classmethod
    def normalize_paths(cls, v: str | Path) -> str:
        """Normalize path strings by expanding user and stripping whitespace.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        str
            The normalized path as a string.
        """
        return str(Path(v).expanduser()).strip()

    # Ensure wanda_bin ends with "**\\"
    @field_validator("wanda_bin")
    @classmethod
    def ensure_wanda_bin_format(cls, v: str | Path) -> str:
        """Ensure wanda_bin path ends with double backslash.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        str
            The formatted path as a string.
        """
        path_str = str(Path(v).expanduser()).strip()
        if not path_str.endswith("\\\\"):
            path_str += "\\\\"
        return path_str


class RunContext(BaseModel):
    """Context information for a model run.

    Attributes
    ----------
    run_id : str
        Unique identifier for the run.
    timestamp : str
        Timestamp of the run in ISO format.
    root_dir : str | Path
        Root directory for the run.
    analysis_meta : AnalysisMeta
        Global analysis metadata associated with the run.
    description : Optional[str]
        Optional description of the run.
    metadata : Dict[str, Any]
        Additional metadata for the run.
    """

    model_config = ConfigDict(extra="forbid")

    # Information about this run
    run_id: str = Field(..., description="Unique identifier for the run.")
    timestamp: str = Field(..., description="Timestamp of the run in ISO format.")
    root_dir: str | Path = Field(..., description="Root directory for the run.")

    # Global analysis metadata
    analysis_meta: AnalysisMeta = Field(
        default_factory=AnalysisMeta,
        description="Global analysis metadata associated with the run.",
    )

    # Optional description and metadata
    description: str | None = Field(default=None, description="Optional description of the run.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the run.",
    )

    @field_validator("timestamp")
    @classmethod
    def ensure_timestamp_string(cls, v: Any) -> str:
        """Ensure timestamp is a string in ISO format.

        Parameters
        ----------
        v : Any
            The input timestamp (could be datetime, str, etc.).

        Returns
        -------
        str
            The timestamp as a string.
        """
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v).strip()

    @field_validator("root_dir")
    @classmethod
    def normalize_paths(cls, v: str | Path) -> str:
        """Normalize path strings by expanding user and stripping whitespace.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        str
            The normalized path as a string.
        """
        return str(Path(v).expanduser()).strip()
