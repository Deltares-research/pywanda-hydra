"""Context objects shared by post-processing case and run steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..scenarios.schema import ScenarioSpecification
from .cache import ParquetCache
from .export import DEFAULT_TABLE_EXPORT_PROPS, build_figure_export_props


@dataclass
class CaseContext:
    """Context passed to per-case post-processing steps."""

    cache: ParquetCache
    scenario: ScenarioSpecification
    case_dir: Path
    export_figure_props: dict[str, dict[str, Any]] = field(
        default_factory=build_figure_export_props
    )
    export_table_props: dict[str, dict[str, Any]] = field(
        default_factory=lambda: dict(DEFAULT_TABLE_EXPORT_PROPS)
    )


@dataclass(frozen=True)
class RunStepContext:
    """Context passed to run-level post-processing steps."""

    run_root: Path
    run_id: str
    case_results: tuple[dict[str, Any], ...]
