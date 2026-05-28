"""Run configuration loader and top-level config model.

Loads a run configuration from a YAML file and validates it into a
structured Pydantic model. The config defines model specification,
execution settings, and scenario source paths.
"""

from __future__ import annotations

import hashlib
import json
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ModelSpecification, RunContext

# ---------------------------------------------------------------------------
# Execution settings
# ---------------------------------------------------------------------------


class ExecutionConfig(BaseModel):
    """Execution mode and worker configuration.

    Attributes:
        mode: Execution strategy.
        n_workers: Number of parallel workers (only used when mode != sequential).
        resume: Whether to skip already-completed cases.
        methodology: Post-processing methodology name (default uses standard pipeline).
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["sequential", "multiprocessing"] = "sequential"
    n_workers: int = Field(default=1, ge=1)
    resume: bool = False
    methodology: str = "default"


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

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
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


class RunConfig(BaseModel):
    """Top-level run configuration combining all settings.

    Attributes:
        run_id: Unique run identifier (auto-generated if not provided).
        output_root: Root directory for run outputs.
        description: Optional human-readable description.
        execution: Execution mode and parallelism settings.
        model: WANDA model specification.
        scenario_file: Path to the scenario definition file (XLS).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        description="Unique run identifier.",
    )
    output_root: str | Path = Field(
        default="./runs",
        description="Root directory for run outputs.",
    )
    description: Optional[str] = None

    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    model: ModelSpecification
    scenario_file: str | Path = Field(..., description="Path to the scenario definition file.")

    @field_validator("output_root", "scenario_file")
    @classmethod
    def normalize_path(cls, v: str | Path) -> str:
        """Normalize paths by expanding user home."""
        return str(Path(v).expanduser()).strip()


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
        raise ValueError(f"Unsupported config format: '{ext}'. Use .yaml, .yml, or .json.")

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping, got: {type(raw).__name__}")

    return RunConfig.model_validate(raw)


def build_run_context(config: RunConfig) -> RunContext:
    """Build a RunContext from a RunConfig.

    Args:
        config: The validated run configuration.

    Returns:
        RunContext with populated fields.
    """
    run_root = Path(config.output_root) / config.run_id
    return RunContext(
        run_id=config.run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        root_dir=str(run_root),
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
