"""CasePlan — immutable description of everything a worker needs to run one case."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import ModelSpecification
from ..scenarios.schema import AnalysisMeta, ScenarioSpecification


@dataclass(frozen=True, slots=True)
class CasePlan:
    """Immutable plan for executing a single scenario case.

    Contains all information the worker needs: model spec, scenario
    parameters, output specs, and directory paths. Serializable for
    multiprocessing transfer.

    Attributes:
        case_id: Unique identifier for this case (e.g. "003_valve_closed").
        case_dir: Absolute path to the case output directory.
        model_spec: Model specification (paths, run flags, global overrides).
        scenario: The full scenario specification.
        analysis_metadata: Analysis-level metadata shared by all cases.
        workflow_name: Post-processing workflow name.
        workflow_params: Post-processing workflow parameters.
        attempt: Current attempt number (for retries).
        config_hash: SHA-256 hash of the plan for idempotency checks.
    """

    case_id: str
    case_dir: Path
    model_spec: ModelSpecification
    scenario: ScenarioSpecification
    analysis_metadata: AnalysisMeta = field(default_factory=AnalysisMeta)
    workflow_name: str = "default"
    workflow_params: dict[str, Any] = field(default_factory=dict)
    attempt: int = 1
    config_hash: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Compute config_hash if not provided."""
        if not self.config_hash:
            # Use object.__setattr__ because frozen
            object.__setattr__(self, "config_hash", self._compute_hash())

    def _compute_hash(self) -> str:
        """Compute a deterministic hash of the plan configuration."""
        model_bytes_hash = hashlib.sha256(self.model_spec.model_path.read_bytes()).hexdigest()
        payload = {
            "v": 2,
            "model_path": str(self.model_spec.model_path),
            "model_bytes_sha256": model_bytes_hash,
            "workflow_name": self.workflow_name,
            "workflow_params": self.workflow_params,
            "run_steady": self.model_spec.run_steady,
            "run_unsteady": self.model_spec.run_unsteady,
            "parameters": [ch.model_dump(mode="json") for ch in self.scenario.parameter_changes],
            "post_processing": self.scenario.post_processing.model_dump(mode="json"),
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build_case_plans(
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
    run_root: Path,
    workflow_name: str = "default",
    workflow_params: dict[str, Any] | None = None,
    analysis_metadata: AnalysisMeta | None = None,
) -> list[CasePlan]:
    """Build CasePlan objects for all included scenarios.

    Args:
        model_spec: The model specification for the run.
        scenarios: All loaded scenarios (filtering by include happens here).
        run_root: Root directory for the run output.
        workflow_name: Post-processing workflow name.
        workflow_params: Post-processing workflow parameters.
        analysis_metadata: Analysis-level metadata shared by all cases.

    Returns:
        List of CasePlan objects for included scenarios.
    """
    meta = analysis_metadata if analysis_metadata is not None else AnalysisMeta()
    plans: list[CasePlan] = []
    for scenario in scenarios:
        if not scenario.include:
            continue

        case_id = scenario.name
        case_dir = run_root / "scenarios" / case_id

        plans.append(
            CasePlan(
                case_id=case_id,
                case_dir=case_dir,
                model_spec=model_spec,
                scenario=scenario,
                analysis_metadata=meta,
                workflow_name=workflow_name,
                workflow_params=dict(workflow_params or {}),
            )
        )
    return plans
