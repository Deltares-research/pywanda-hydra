"""Configuration models for PyWANDA Hydra."""

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
    model_path : Path
        Path to .wdi (or base path).
    wanda_bin : Path
        Path to WANDA binaries and executables.
    base_model_name : str
        Name of the wanda base model (without .wdi extension).

    readonly : bool, optional
        If model output exists, the model is treated as read-only (default is True).
    upgrade : bool, optional
        Upgrade the model to the installed WANDA version on open (default is False).

    run_steady : bool, optional
        Whether to run steady simulations (default is True).
    run_unsteady : bool, optional
        Whether to run unsteady simulations (default is False).
    """

    model_config = ConfigDict(extra="forbid")

    model_path: Path = Field(..., description="Path to .wdi (or base path)")
    wanda_bin: Path = Field(..., description="Path to WANDA binaries and executables")
    base_model_name: str

    # Run settings
    readonly: bool = Field(
        default=True,
        description="If model output exists, the model is treated as read-only.",
    )
    upgrade: bool = Field(
        default=False,
        description="Upgrade the model to the installed WANDA version on open.",
    )

    # Optional execution settings you may want centrally:
    run_steady: bool = True
    run_unsteady: bool = False

    # Genneral settings to apply before scenarios (global tweaks)
    global_overrides: list[ParameterChange] = Field(
        default_factory=list,
        description="Global parameter changes to apply before scenarios changes.",
    )

    @field_validator("model_path", mode="before")
    @classmethod
    def normalize_paths(cls, v: str | Path) -> Path:
        """Normalize paths by expanding user and stripping whitespace.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        Path
            The normalized path.
        """
        return Path(str(v).strip()).expanduser()

    # Ensure wanda_bin ends with "**\\"
    @field_validator("wanda_bin", mode="before")
    @classmethod
    def ensure_wanda_bin_format(cls, v: str | Path) -> Path:
        """Normalize wanda_bin path.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        Path
            The normalized path.
        """
        return Path(str(v).strip()).expanduser()

    # Ensure base_model_name has no WANDA file suffixes (e.g., .wdi, .wdo, .wdx).
    @field_validator("base_model_name", mode="before")
    @classmethod
    def ensure_base_model_name_format(cls, v: str) -> str:
        """Normalize base_model_name by stripping WANDA file suffixes.

        Only WANDA extensions (e.g., .wdi, .wdo, .wdx) are removed; other
        dot-segments (e.g. "model_v4.8") are preserved.

        Parameters
        ----------
        v : str
            The input base model name.

        Returns
        -------
        str
            The normalized base model name without WANDA file suffixes.
        """
        # Lowercase only: compared against a lowercased suffix below.
        wanda_suffixes = {
            ".wdi",
            ".wdo",
            ".wdx",
            "._sm",
            "._um",
            ".__i",
            ".__r",
        }
        name = Path(str(v).strip()).name
        while (suffix := Path(name).suffix.lower()) in wanda_suffixes:
            name = name[: -len(suffix)]

        normalized = name.strip()
        if not normalized:
            raise ValueError("base_model_name must contain a non-empty name.")
        return normalized


class RunContext(BaseModel):
    """Context information for a model run.

    Attributes
    ----------
    run_id : str
        Unique identifier for the run.
    timestamp : str
        Timestamp of the run in ISO format.
    root_dir : Path
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
    root_dir: Path = Field(..., description="Root directory for the run.")

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

    @field_validator("root_dir", mode="before")
    @classmethod
    def normalize_paths(cls, v: str | Path) -> Path:
        """Normalize paths by expanding user and stripping whitespace.

        Parameters
        ----------
        v : str | Path
            The input path.

        Returns
        -------
        Path
            The normalized path.
        """
        return Path(str(v).strip()).expanduser()
