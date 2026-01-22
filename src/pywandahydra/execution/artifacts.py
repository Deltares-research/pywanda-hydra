"""Execution artifacts management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..config.models import ModelSpecification, RunContext
from ..scenarios.schema import ScenarioSpecification


def create_run_directories(
    context_object: RunContext,
) -> None:
    """Create necessary directories for the run.

    Parameters
    ----------
    context_object : RunContext
        The run context containing directory paths.
    """
    # Extract root directory from context
    root = Path(context_object.root_dir)
    # Create directories
    directories_to_create = [
        "figures",
        "logs",
        "tables",
        "scenarios",
    ]
    for dir_name in directories_to_create:
        dir_path = root / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)


def write_run_log(
    context_object: RunContext,
    model_spec: ModelSpecification,
    scenarios: List[ScenarioSpecification],
) -> None:
    """Write a JSON log file summarizing the run configuration.

    Parameters
    ----------
    context_object : RunContext
        The run context containing directory paths.
    model_spec : ModelSpecification
        The model specification used for the run.
    scenarios : List[ScenarioSpecification]
        The list of scenario specifications for the run.
    """
    log_data: Dict[str, Any] = {
        "run_context": context_object.model_dump(mode="json"),
        "model_specification": model_spec.model_dump(mode="json"),
        "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
    }

    log_path = (
        Path(context_object.root_dir)
        / "logs"
        / f"{context_object.run_id}_log_{context_object.timestamp}.json"
    )
    with log_path.open("w", encoding="utf-8") as log_file:
        json.dump(log_data, log_file, indent=4, default=str)
