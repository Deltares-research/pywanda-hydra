"""Prepared execution plans and legacy-engine conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config.models import RunConfiguration
from ..scenarios.models.document import ScenarioDocument
from .case_plan import CasePlan


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
