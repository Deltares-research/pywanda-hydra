"""Data structures and functions for loading scenario definitions from files."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from . import sources as _sources  # noqa: F401
from .schema import ScenarioSpecification
from .sources.base import SourceValidationIssue, get_source_for_extension

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
    output_sheet: str | None = "Output"
    rplots_sheet: str | None = "Rplots"
    tplots_sheet: str | None = "Tplots"

    # Strict validation: raise on missing/malformed post-processing sheets,
    # missing required columns, duplicate route titles, or duplicate
    # (component, property) entries in the Output sheet. When False (default),
    # malformed rows / missing sheets are silently skipped (legacy behavior).
    strict_validation: bool = False


def load_scenarios(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> list[ScenarioSpecification]:
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

    # Use the registry to find the appropriate source.
    source_cls = get_source_for_extension(path.suffix)

    # Instantiate and load. The ScenarioSource protocol has no __init__, so
    # mypy can't see that concrete sources accept `options`.
    source = source_cls(options=opts)  # type: ignore[call-arg]
    scenarios = source.load(path)
    logger.info("Loaded %d scenarios from %s", len(scenarios), path.name)
    return scenarios


def check_scenario_file(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> list[SourceValidationIssue]:
    """Run structural preflight checks on a scenario definition file.

    Reports missing sheets and missing required columns without raising and
    without fully parsing the file, so all problems surface in one pass.

    Args:
        path: Path to the scenario file.
        options: Optional ScenarioLoadOptions (used by the XLS source).

    Returns:
        All structural issues found. Empty if the file is well-formed, or if
        the source backend does not implement structural checks.

    Raises:
        ValueError: If the file extension is unsupported.
        FileNotFoundError: If the file does not exist.
    """
    opts = options or ScenarioLoadOptions()
    path = Path(path) if isinstance(path, str) else path

    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    source_cls = get_source_for_extension(path.suffix)
    source = source_cls(options=opts)  # type: ignore[call-arg]
    check_structure = getattr(source, "check_structure", None)
    if check_structure is None:
        return []
    return cast(list[SourceValidationIssue], check_structure(path))


def assert_scenario_file_valid(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> None:
    """Raise a single error with all structural preflight findings, if any.

    Args:
        path: Path to the scenario file.
        options: Optional ScenarioLoadOptions (used by the XLS source).

    Raises:
        ValueError: If the file has any structural issues, or is an
            unsupported extension.
        FileNotFoundError: If the file does not exist.
    """
    issues = check_scenario_file(path, options=options)
    if not issues:
        return

    lines = [f"Scenario file failed preflight checks ({path}):"]
    for issue in issues:
        lines.append(f"- [{issue.sheet}] {issue.message}")
    raise ValueError("\n".join(lines))
