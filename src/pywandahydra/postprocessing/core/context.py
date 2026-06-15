"""Context objects shared by post-processing case and run steps, and model extraction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...scenarios.schema import ScenarioSpecification
from ...wanda.adapter import WandaAdapter
from ..io.cache import ParquetCache
from ..io.export import DEFAULT_TABLE_EXPORT_PROPS, build_figure_export_props
from ..plotting.renderers.theme import PlotTheme


@dataclass(frozen=True)
class ExtractionContext:
    """Context passed to extractors during model execution.

    Extractors run while the WANDA model session is open, allowing
    access to the live model handle and full adapter API. Results
    are cached after extraction completes.
    """

    model: Any
    """Live pywanda.WandaModel handle."""

    adapter: WandaAdapter
    """Adapter for model operations."""

    scenario: ScenarioSpecification
    """Scenario specification."""

    case_id: str
    """Case identifier."""

    case_dir: Path
    """Case output directory (for logging, metadata)."""

    cache: ParquetCache | None = None
    """Pre-extracted cache (available if prior extractors ran).

    Initially None; after first extractor, updated for subsequent extractors.
    """


@dataclass
class CaseContext:
    """Context passed to per-case post-processing steps."""

    cache: ParquetCache
    scenario: ScenarioSpecification
    case_dir: Path
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
