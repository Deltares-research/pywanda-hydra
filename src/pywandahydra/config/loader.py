"""Run configuration loader and top-level config model.

Loads a run configuration from a YAML file and validates it into a
structured Pydantic model. The config defines model specification,
execution settings, and scenario source paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..scenarios.schema import ScenarioSpecification
from .models import ModelSpecification, RunContext

# ---------------------------------------------------------------------------
# Execution settings
# ---------------------------------------------------------------------------


class MethodologySpec(BaseModel):
    """Config wrapper for methodology name + validated parameter dict."""

    model_config = ConfigDict(extra="forbid")
    name: str = "default"
    params: dict[str, Any] = Field(default_factory=dict)


class ExecutionConfig(BaseModel):
    """Execution mode and worker configuration.

    Attributes:
        mode: Execution strategy.
        n_workers: Number of parallel workers (only used when mode != sequential).
        resume: Whether to skip already-completed cases.
        methodology: Post-processing methodology name + params.
        extractors: List of custom extractors to run during model execution.
        verbose: Enable detailed logging during execution (default False).
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["sequential", "multiprocessing"] = "sequential"
    n_workers: int = Field(default=1, ge=1)
    resume: bool = False
    verbose: bool = False
    methodology: MethodologySpec = Field(default_factory=MethodologySpec)
    extractors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of extractor specs: [{name: str, params: dict}]",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_methodology_str(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("methodology"), str):
            data = dict(data)
            data["methodology"] = {"name": data["methodology"]}
        return data

    @model_validator(mode="after")
    def validate_mode_workers(self) -> ExecutionConfig:
        """Ensure execution mode and worker settings are coherent."""
        if self.mode == "sequential" and self.n_workers != 1:
            raise ValueError(
                "execution.n_workers must be 1 when execution.mode='sequential'"
            )
        return self


# ---------------------------------------------------------------------------
# Provenance (auto-captured)
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    """Auto-captured environment provenance for reproducibility.

    Attributes:
        timestamp: ISO UTC timestamp of the run.
        hostname: Machine hostname.
        os: Operating system description.
        python_version: Python version string.
        platform: Platform identifier.
        pywandahydra_version: Package version.
    """

    model_config = ConfigDict(extra="allow")

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    hostname: str = Field(default_factory=socket.gethostname)
    os: str = Field(default_factory=lambda: f"{platform.system()} {platform.release()}")
    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=platform.platform)
    pywandahydra_version: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if not self.pywandahydra_version:
            try:
                from pywandahydra import __version__

                self.pywandahydra_version = __version__.strip()
            except Exception:
                self.pywandahydra_version = "unknown"


# ---------------------------------------------------------------------------
# Run configuration (top-level)
# ---------------------------------------------------------------------------


class PostProcessingRunConfig(BaseModel):
    """Run-level post-processing overrides applied to every scenario.

    Currently only ``theme`` is supported; when set, it overrides the per-scenario
    theme for all scenarios in the run.
    """

    model_config = ConfigDict(extra="forbid")

    theme: str | None = None


class RunConfig(BaseModel):
    """Top-level run configuration combining all settings.

    Attributes:
        run_id: Unique run identifier (auto-generated if not provided).
        output_root: Root directory for run outputs.
        description: Optional human-readable description.
        execution: Execution mode and parallelism settings.
        model: WANDA model specification.
        scenario_file: Path to the scenario definition file (XLS).
        post_processing: Run-level post-processing overrides (e.g. theme).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        description="Unique run identifier.",
    )
    output_root: Path = Field(
        default=Path("./runs"),
        description="Root directory for run outputs.",
    )
    description: str | None = None

    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    model: ModelSpecification
    scenario_file: Path = Field(
        ..., description="Path to the scenario definition file."
    )
    post_processing: PostProcessingRunConfig = Field(
        default_factory=PostProcessingRunConfig
    )

    @field_validator("output_root", "scenario_file", mode="before")
    @classmethod
    def normalize_path(cls, v: str | Path) -> Path:
        """Normalize paths by expanding user home."""
        return Path(str(v).strip()).expanduser()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_run_config(path: Path | str) -> RunConfig:
    """Load and validate a run configuration from a YAML or JSON file.

    Args:
        path: Path to the configuration file (.yaml, .yml, or .json).

    Returns:
        Validated RunConfig instance.

    Raises:
        ValueError: If the file format is unsupported or validation fails.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    ext = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if ext in (".yaml", ".yml"):
        raw = yaml.safe_load(text)
    elif ext == ".json":
        raw = json.loads(text)
    else:
        raise ValueError(
            f"Unsupported config format: '{ext}'. Use .yaml, .yml, or .json."
        )

    if not isinstance(raw, dict):
        raise ValueError(
            f"Config file must contain a mapping, got: {type(raw).__name__}"
        )

    return RunConfig.model_validate(raw)


def validate_run_paths(config: RunConfig, *, config_dir: Path) -> None:
    """Validate runtime-critical paths before executing a run.

    Also resolves relative paths to absolute paths based on config_dir.

    Args:
        config: Validated run configuration.
        config_dir: Directory that contains the run config file.

    Raises:
        ValueError: If any path is invalid or not accessible.
    """
    model_path = config.model.model_path
    if not model_path.is_absolute():
        model_path = config_dir / model_path

    if model_path.suffix.lower() != ".wdi":
        raise ValueError(
            f"model.model_path must point to a .wdi file, got: {model_path}"
        )
    if not model_path.exists():
        raise ValueError(f"model.model_path does not exist: {model_path}")

    wanda_bin = config.model.wanda_bin
    if not wanda_bin.is_absolute():
        wanda_bin = config_dir / wanda_bin
    if not wanda_bin.exists() or not wanda_bin.is_dir():
        raise ValueError(f"model.wanda_bin must be an existing directory: {wanda_bin}")

    scenario_file = config.scenario_file
    if not scenario_file.is_absolute():
        scenario_file = config_dir / scenario_file
    if not scenario_file.exists():
        raise ValueError(f"scenario_file does not exist: {scenario_file}")

    output_root = config.output_root
    if not output_root.is_absolute():
        output_root = config_dir / output_root
    output_root.mkdir(parents=True, exist_ok=True)
    if not os.access(output_root, os.W_OK):
        raise ValueError(f"output_root is not writable: {output_root}")

    # Update config object with absolute paths
    config.model.model_path = model_path
    config.model.wanda_bin = wanda_bin
    config.scenario_file = scenario_file
    config.output_root = output_root


def apply_post_processing_overrides(
    config: RunConfig, scenarios: list[ScenarioSpecification]
) -> None:
    """Apply run-level post-processing overrides in place.

    Validates the theme against the registered theme registry and overrides
    each scenario's per-scenario theme when a top-level theme is configured.
    """
    theme_name = config.post_processing.theme
    if theme_name is None:
        return

    from ..postprocessing.plotting.themes import list_themes

    known = list_themes()
    if theme_name not in known:
        raise ValueError(
            f"post_processing.theme '{theme_name}' is not registered. "
            f"Known themes: {known}"
        )
    for scenario in scenarios:
        scenario.post_processing.theme = theme_name


def build_run_context(config: RunConfig) -> RunContext:
    """Build a RunContext from a RunConfig.

    Args:
        config: The validated run configuration.

    Returns:
        RunContext with populated fields.
    """
    run_root = config.output_root / config.run_id
    return RunContext(
        run_id=config.run_id,
        timestamp=datetime.now(UTC).strftime("%Y-%m-%d_%H-%M"),
        root_dir=run_root,
        description=config.description,
    )


def config_hash(config: RunConfig) -> str:
    """Compute a deterministic hash of the run configuration.

    Args:
        config: The run configuration.

    Returns:
        Hash string prefixed with "sha256:".
    """
    raw = config.model_dump(mode="json")
    serialized = json.dumps(raw, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(serialized.encode()).hexdigest()
