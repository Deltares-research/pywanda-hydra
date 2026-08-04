"""Context objects shared by post-processing case and run steps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...results import ParquetResultStore
from ...scenarios import AnalysisMeta, ScenarioSpecification
from ..figures.export import build_figure_export_props
from ..figures.theme import PlotTheme
from ..tables.export import DEFAULT_TABLE_EXPORT_PROPS


@dataclass
class CaseContext:
    """Context passed to per-case post-processing steps."""

    store: ParquetResultStore
    scenario: ScenarioSpecification
    case_dir: Path
    analysis_metadata: AnalysisMeta = field(default_factory=AnalysisMeta)
    theme: PlotTheme = field(default_factory=PlotTheme)
    export_figure_props: dict[str, dict[str, Any]] = field(
        default_factory=build_figure_export_props
    )
    export_table_props: dict[str, dict[str, Any]] = field(
        default_factory=lambda: dict(DEFAULT_TABLE_EXPORT_PROPS)
    )


@dataclass(frozen=True)
class PostProcessingRunContext:
    """Context passed to run-level post-processing steps."""

    run_root: Path
    run_id: str
    case_results: tuple[Mapping[str, Any], ...]
