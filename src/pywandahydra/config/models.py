"""Authored run-configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _AuthoredModel(BaseModel):
    """Base model that rejects unknown authored configuration keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelConfiguration(_AuthoredModel):
    """Authored WANDA model settings."""

    path: Path
    wanda_bin: Path
    upgrade: bool = False

    @field_validator("path", mode="before")
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


class SimulationConfiguration(_AuthoredModel):
    """Authored simulation switches."""

    steady: bool = True
    unsteady: bool = False


class ExecutionConfiguration(_AuthoredModel):
    """Authored execution settings."""

    workers: int = Field(default=1, ge=1)
    resume: bool = False


class OutputConfiguration(_AuthoredModel):
    """Authored output settings."""

    theme: str | None = None
    figure_formats: tuple[str, ...] = ()
    table_formats: tuple[str, ...] = ()


class RunConfiguration(_AuthoredModel):
    """Complete user-authored run configuration."""

    run_id: str
    output_root: Path = Path("./runs")
    description: str | None = None
    scenario_file: Path
    model: ModelConfiguration
    simulation: SimulationConfiguration = Field(default_factory=SimulationConfiguration)
    execution: ExecutionConfiguration = Field(default_factory=ExecutionConfiguration)
    outputs: OutputConfiguration = Field(default_factory=OutputConfiguration)

    @field_validator("output_root", "scenario_file", mode="before")
    @classmethod
    def normalize_path(cls, value: str | Path) -> Path:
        return Path(str(value).strip()).expanduser()
