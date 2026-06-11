"""Utility functions for a wanda model."""

# wanda_param_analysis/wanda/model_io.py
from __future__ import annotations

import shutil
from pathlib import Path


def prepare_scenario_model(
    base_model_path: Path,
    scenario_dir: str | Path,
    scenario_name: str,
    *,
    readonly: bool = True,
) -> Path:
    """Scenario-specific WANDA model.

    Routine copies the base .wdi and .wdx files into a scenario-specific
    directory, naming them according to the scenario.

    Parameters
    ----------
    base_model_path : Path
        Path to the base .wdi model file.
    scenario_dir : str | Path
        Directory where the scenario model will be created.
    readonly : bool, optional
        If True, the model files are set to read-only (default is True).
    scenario_name : str
        Name of the scenario, used to name the model files.
    """
    # Validate and prepare paths
    base_wdi = base_model_path
    if base_wdi.suffix.lower() != ".wdi":
        raise ValueError(f"Expected .wdi model path, got: {base_wdi}")

    # Create target directory
    scenario_dir = Path(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # Name the scenario model deterministically
    target_wdi = scenario_dir / f"{base_wdi.stem}_{scenario_name}.wdi"
    target_wdx = target_wdi.with_suffix(".wdx")

    # Source companion files
    src_wdx = base_wdi.with_suffix(".wdx")

    # If readonly, and .wdo exists -> skip copying
    if readonly and target_wdi.exists():
        return target_wdi

    # Otherwise, remove existing files if any
    if target_wdi.exists():
        target_wdi.unlink()
    if target_wdx.exists():
        target_wdx.unlink()

    # Copy required files
    shutil.copyfile(base_wdi, target_wdi)
    if src_wdx.exists():
        shutil.copyfile(src_wdx, target_wdx)

    return target_wdi
