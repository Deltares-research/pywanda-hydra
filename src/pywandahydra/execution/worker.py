"""Worker module to execute a single scenario on a given model using Wanda."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pyexpat import model

from ..config.models import ModelSpecification, RunContext
from ..scenarios.schema import ScenarioSpecification
from ..wanda.api import apply_parameter_change
from ..wanda.create_scenario import copy_model_to_directory
from ..wanda.session import wanda_session


def run_one_scenario(
    model_specifications: ModelSpecification, scenario: ScenarioSpecification, ctx: RunContext
) -> Dict[str, Any]:
    # Create scenario directory
    scenario_dir = Path(ctx.root_dir) / "scenarios" / scenario.meta.name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # Createa a scenario-specific model copy
    scenario_model_path = copy_model_to_directory(
        base_model_path=model_specifications.model_path,
        scenario_dir=scenario_dir,
        scenario_name=scenario.meta.name,
    )

    try:
        with wanda_session(model_specifications, model_path=str(scenario_model_path)) as wmodel:
            # Apply global overrides (optional list)
            for ch in model_specifications.global_overrides:
                apply_parameter_change(wmodel, ch)

            # Apply scenario parameters
            for ch in scenario.parameters:
                apply_parameter_change(wmodel, ch)

            # Run
            if model_specifications.run_steady:
                wmodel.save_model_input()
                wmodel.run_steady()

            if (
                model_specifications.run_unsteady
                and wmodel.get_property("Simulation time").get_scalar_float() > 0
            ):
                wmodel.run_unsteady()

            # Persist minimal outcome; expand later (KPIs, series, PDFs)
            return {
                "scenario": scenario.meta.name,
                "number": scenario.meta.number,
                "success": True,
                "scenario_dir": str(scenario_dir),
            }

    except Exception as e:
        return {
            "scenario": scenario.meta.name,
            "number": scenario.meta.number,
            "success": False,
            "error": str(e),
            "scenario_dir": str(scenario_dir),
        }
