"""Serializable plans for prepared runs and individual case execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..config.models import RunConfiguration
from ..scenarios import AnalysisMeta, ScenarioSpecification
from ..scenarios.models.document import ScenarioDocument


class ModelSpecification(BaseModel):
    """Resolved model settings used by a serializable case plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_path: Path
    wanda_bin: Path
    upgrade: bool = False
    run_steady: bool = True
    run_unsteady: bool = False


@dataclass(frozen=True, slots=True)
class CasePlan:
    """Immutable, pickle-safe input for executing one scenario."""

    case_id: str
    case_dir: Path
    model_spec: ModelSpecification
    scenario: ScenarioSpecification
    analysis_metadata: AnalysisMeta = field(default_factory=AnalysisMeta)
    config_hash: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.config_hash:
            object.__setattr__(self, "config_hash", self._compute_hash())

    def _compute_hash(self) -> str:
        payload = {
            "model_sha256": hashlib.sha256(self.model_spec.model_path.read_bytes()).hexdigest(),
            "upgrade": self.model_spec.upgrade,
            "run_steady": self.model_spec.run_steady,
            "run_unsteady": self.model_spec.run_unsteady,
            "parameters": [
                change.model_dump(mode="json") for change in self.scenario.parameter_changes
            ],
            "post_processing": self.scenario.post_processing.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def build_case_plans(
    model_spec: ModelSpecification,
    scenarios: tuple[ScenarioSpecification, ...] | list[ScenarioSpecification],
    run_root: Path,
    analysis_metadata: AnalysisMeta | None = None,
) -> tuple[CasePlan, ...]:
    """Build a plan for each included scenario without touching case directories."""
    metadata = analysis_metadata or AnalysisMeta()
    return tuple(
        CasePlan(
            case_id=scenario.name,
            case_dir=run_root / "scenarios" / scenario.name,
            model_spec=model_spec,
            scenario=scenario,
            analysis_metadata=metadata,
        )
        for scenario in scenarios
        if scenario.include
    )


@dataclass(frozen=True, slots=True)
class RunPlan:
    """Prepared, side-effect-free input for one run execution."""

    configuration: RunConfiguration
    config_path: Path
    model_path: Path
    wanda_bin: Path
    run_dir: Path
    scenario_document: ScenarioDocument
    cases: tuple[CasePlan, ...]
