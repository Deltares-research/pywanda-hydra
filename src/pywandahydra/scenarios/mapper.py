"""Data structures and functions for loading scenario definitions from files."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .schema import ScenarioSpecification
from .sources.base import get_source_for_extension
from .sources.xls import read_scenarios_from_excel

logger = logging.getLogger(__name__)


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

    Auto-selects the parser based on file extension via the ScenarioSource
    registry. Currently supports .xls/.xlsx/.xlsm. The registry is
    extensible — new sources can be added by implementing the ScenarioSource
    protocol and decorating with @register_source.

    Args:
        path: Path to the scenario file.
        options: Optional ScenarioLoadOptions (used by the XLS source).

    Returns:
        Canonical scenario definitions (source-agnostic).

    Raises:
        ValueError: If the file extension is unsupported.
        FileNotFoundError: If the file does not exist.
    """
    opts = options or ScenarioLoadOptions()
    path = Path(path) if isinstance(path, str) else path

    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    # Use registry to find the appropriate source
    try:
        source_cls = get_source_for_extension(path.suffix)
    except ValueError:
        # Fallback: direct call for backwards compatibility with XLS
        if path.suffix in {".xls", ".xlsx", ".xlsm"}:
            return read_scenarios_from_excel(path, opts)
        raise

    # Instantiate and load
    source = source_cls(options=opts)  # type: ignore[call-arg]
    scenarios = source.load(path)
    logger.info("Loaded %d scenarios from %s", len(scenarios), path.name)
    return scenarios
