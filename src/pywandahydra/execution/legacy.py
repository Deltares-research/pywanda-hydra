"""Private compatibility contracts required by the pre-S12 execution engine."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..scenarios import AnalysisMeta


class ModelSpecification(BaseModel):
    """Legacy engine model settings, constructed only from a prepared plan."""

    model_config = ConfigDict(extra="forbid")

    model_path: Path
    wanda_bin: Path
    base_model_name: str
    reuse_existing_data: bool = True
    upgrade: bool = False
    run_steady: bool = True
    run_unsteady: bool = False


class RunContext(BaseModel):
    """Legacy engine run context, constructed only from a prepared plan."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    timestamp: str
    root_dir: Path
    analysis_meta: AnalysisMeta = Field(default_factory=AnalysisMeta)
    description: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
