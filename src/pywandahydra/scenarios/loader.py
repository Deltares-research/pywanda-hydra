"""Explicit scenario-loader dispatch by file extension."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .excel.loader import load_excel_document
from .excel.validation import check_xls_structure
from .models.document import ScenarioDocument, ScenarioWarning
from .models.scenario import ScenarioSpecification


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


_LOADERS = {
    ".xls": load_excel_document,
    ".xlsx": load_excel_document,
    ".xlsm": load_excel_document,
}

_STRUCTURE_CHECKERS = {
    ".xls": check_xls_structure,
    ".xlsx": check_xls_structure,
    ".xlsm": check_xls_structure,
}

class _DocumentLoader(Protocol):
    def __call__(
        self,
        path: Path | str,
        opts: ScenarioLoadOptions,
        *,
        strict: bool,
    ) -> ScenarioDocument: ...


_StructureChecker = Callable[[Path | str, ScenarioLoadOptions], list[ScenarioWarning]]


def _normalize_path(path: Path | str) -> Path:
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        raise FileNotFoundError(f"Scenario file not found: {p}")
    return p


def _resolve_loader(path: Path) -> _DocumentLoader:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        supported = sorted(_LOADERS.keys())
        raise ValueError(
            f"Unsupported scenario file extension: '{path.suffix.lower()}'. Supported: {supported}"
        )
    return loader


def _resolve_structure_checker(path: Path) -> _StructureChecker:
    checker = _STRUCTURE_CHECKERS.get(path.suffix.lower())
    if checker is None:
        supported = sorted(_STRUCTURE_CHECKERS.keys())
        raise ValueError(
            f"Unsupported scenario file extension: '{path.suffix.lower()}'. Supported: {supported}"
        )
    return checker


def load_scenario_document(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
    strict: bool | None = None,
) -> ScenarioDocument:
    """Load a scenario workbook into a typed ``ScenarioDocument`` aggregate."""
    opts = options or ScenarioLoadOptions()
    strict_mode = opts.strict_validation if strict is None else strict
    p = _normalize_path(path)
    loader = _resolve_loader(p)
    return loader(p, opts, strict=strict_mode)


def load_scenarios(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
    strict: bool | None = None,
) -> list[ScenarioSpecification]:
    """Load scenarios from a workbook document."""
    document = load_scenario_document(path, options=options, strict=strict)
    return list(document.scenarios)


def check_scenario_file(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> list[ScenarioWarning]:
    """Run structural preflight checks on a scenario workbook."""
    opts = options or ScenarioLoadOptions()
    p = _normalize_path(path)
    checker = _resolve_structure_checker(p)
    return checker(p, opts)


def assert_scenario_file_valid(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> None:
    """Raise a single error with all structural preflight findings, if any."""
    issues = check_scenario_file(path, options=options)
    if not issues:
        return

    lines = [f"Scenario file failed preflight checks ({path}):"]
    for issue in issues:
        lines.append(f"- [{issue.sheet}] {issue.message}")
    raise ValueError("\n".join(lines))
