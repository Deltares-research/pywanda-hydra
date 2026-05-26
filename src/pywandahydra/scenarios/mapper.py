"""Data structures and functions for loading scenario definitions from files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .schema import ScenarioSpecification
from .sources.xls import read_scenarios_from_excel


@dataclass(frozen=True)
class ScenarioLoadOptions:
    """Scenario load options for XLS source."""

    cases_sheet: str = "Cases"
    cases_header_row_count: int = 1
    cases_property_row_index: int = 0  # row 0 of input_data

    nan_means_skip_parameter: bool = True

    # Global metadata columns
    global_description_col: str = "Description"
    global_wanda_version_col: str = "Extra"
    global_project_number_col: str = "Include"

    # Post-processing sheet names (set to None to skip)
    output_sheet: Optional[str] = "Output"
    rplots_sheet: Optional[str] = "Rplots"


def load_scenarios(
    path: Path | str,
    *,
    options: Optional[ScenarioLoadOptions] = None,
) -> List[ScenarioSpecification]:
    """Load scenarios from a scenario definition file.

    Method is auto-selected based on file extension.

    Parameters
    ----------
    path
        Path to the scenario file (.xlsx/.xlsm for source='xls', .yaml/.yml for source='yaml').
    options
        Optional ScenarioLoadOptions. If None, defaults are used.

    Returns
    -------
    List[ScenarioSpecification]
        Canonical scenario definitions (source-agnostic).
    """
    opts = options or ScenarioLoadOptions()

    # Ensure path is a Path object
    path = Path(path) if isinstance(path, str) else path

    # Auto-select source based on file extension
    if path.suffix in {".xls", ".xlsx", ".xlsm"}:
        return read_scenarios_from_excel(path, opts)
    else:
        raise ValueError(f"Unsupported file extension: {path.suffix}")
