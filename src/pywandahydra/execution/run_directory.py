"""Case directory locations and pure recovery decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..results import DataRequirements, ResultInventory
from .status import CaseStatus

RecoveryAction = Literal["simulate", "postprocess", "skip"]


def case_data_directory(case_dir: Path) -> Path:
    """Return the durable result-store directory for a case."""
    return case_dir / "data"


def recovery_decision(
    *,
    status: CaseStatus | None,
    simulation_fingerprint: str,
    output_fingerprint: str,
    result_store_complete: bool,
    inventory: ResultInventory | None,
    requirements: DataRequirements,
    outputs_current: bool,
) -> RecoveryAction:
    """Choose recovery action from explicit status, raw-data, and output facts."""
    if status is None or status.simulation_status != "succeeded":
        return "simulate"
    if status.simulation_fingerprint != simulation_fingerprint:
        return "simulate"
    if not result_store_complete or inventory is None or not inventory.satisfies(requirements):
        return "simulate"
    if status.postprocessing_status in {"failed", "pending", "running"}:
        return "postprocess"
    if status.output_fingerprint != output_fingerprint or not outputs_current:
        return "postprocess"
    return "skip"
