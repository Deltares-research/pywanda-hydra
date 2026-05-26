"""CasePlan — immutable description of everything a worker needs to run one case."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..config.models import ModelSpecification
from ..scenarios.schema import ScenarioSpecification


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
        attempt: Current attempt number (for retries).
        config_hash: SHA-256 hash of the plan for idempotency checks.
    """

    case_id: str
    case_dir: Path
    model_spec: ModelSpecification
    scenario: ScenarioSpecification
    attempt: int = 1
    config_hash: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Compute config_hash if not provided."""
        if not self.config_hash:
            # Use object.__setattr__ because frozen
            object.__setattr__(self, "config_hash", self._compute_hash())

    def _compute_hash(self) -> str:
        """Compute a deterministic hash of the plan configuration."""
        payload = {
            "case_id": self.case_id,
            "model_path": str(self.model_spec.model_path),
            "run_steady": self.model_spec.run_steady,
            "run_unsteady": self.model_spec.run_unsteady,
            "global_overrides": [
                ch.model_dump(mode="json") for ch in self.model_spec.global_overrides
            ],
            "parameters": [ch.model_dump(mode="json") for ch in self.scenario.parameters],
            "outputs": [s.model_dump(mode="json") for s in self.scenario.outputs],
            "route_plots": [s.model_dump(mode="json") for s in self.scenario.route_plots],
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build_case_plans(
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
    run_root: Path,
) -> list[CasePlan]:
    """Build CasePlan objects for all included scenarios.

    Args:
        model_spec: The model specification for the run.
        scenarios: All loaded scenarios (filtering by include happens here).
        run_root: Root directory for the run output.

    Returns:
        List of CasePlan objects for included scenarios.
    """
    plans: list[CasePlan] = []
    for scenario in scenarios:
        if not scenario.meta.include:
            continue

        case_id = scenario.meta.name
        case_dir = run_root / "scenarios" / case_id

        plans.append(
            CasePlan(
                case_id=case_id,
                case_dir=case_dir,
                model_spec=model_spec,
                scenario=scenario,
            )
        )
    return plans
