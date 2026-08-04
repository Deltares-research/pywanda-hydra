"""Fixed post-processing routines for case and run result data."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..results import ParquetResultStore
from ..scenarios import AnalysisMeta, ScenarioSpecification
from .figures.case_pdf import render_case_pdf
from .figures.run_pdf import merge_case_figure_pdfs
from .tables.case_minmax import write_case_minmax_table
from .tables.run_minmax import write_run_minmax_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PostProcessingOutcome:
    """The result of one stable post-processing routine."""

    routine_name: str
    status: Literal["succeeded", "skipped", "failed"]
    skip_reason: str | None = None
    error: str | None = None
    created_paths: tuple[Path, ...] = ()


def process_case_results(
    *,
    store: ParquetResultStore,
    scenario: ScenarioSpecification,
    case_dir: Path,
    analysis_metadata: AnalysisMeta | None = None,
) -> tuple[PostProcessingOutcome, ...]:
    """Process one case's configured tables and figures in fixed order."""
    metadata = analysis_metadata or AnalysisMeta()
    outcomes: list[PostProcessingOutcome] = []

    if scenario.post_processing.tables.minmax:
        outcomes.append(
            _run_routine(
                "case_minmax_table",
                lambda: write_case_minmax_table(
                    scenario.post_processing.tables.minmax,
                    store,
                    case_dir,
                ),
            )
        )
    else:
        outcomes.append(_skipped("case_minmax_table", "no MIN/MAX table specifications"))

    figures = scenario.post_processing.figures
    if figures.routes or figures.time_series:
        outcomes.append(
            _run_routine(
                "case_figure_pdf",
                lambda: _as_paths(
                    render_case_pdf(
                        store=store,
                        scenario=scenario,
                        case_dir=case_dir,
                        analysis_metadata=metadata,
                    )
                ),
            )
        )
    else:
        outcomes.append(_skipped("case_figure_pdf", "no figure specifications"))

    return tuple(outcomes)


def process_run_results(*, run_root: Path, run_id: str) -> tuple[PostProcessingOutcome, ...]:
    """Process run-level tables and figures in fixed order."""
    scenarios_dir = run_root / "scenarios"
    outcomes = (
        _run_routine(
            "run_minmax_table",
            lambda: write_run_minmax_table(scenarios_dir, run_root / "tables", run_id),
        ),
        _run_routine(
            "run_figure_pdf",
            lambda: _as_paths(
                merge_case_figure_pdfs(
                    scenarios_dir,
                    run_root / "figures" / f"{run_id}_merged.pdf",
                )
            ),
        ),
    )
    return tuple(_skip_empty_output(outcome) for outcome in outcomes)


def _run_routine(
    routine_name: str,
    routine: Callable[[], tuple[Path, ...]],
) -> PostProcessingOutcome:
    try:
        return PostProcessingOutcome(
            routine_name=routine_name,
            status="succeeded",
            created_paths=routine(),
        )
    except Exception as exc:
        logger.exception("Post-processing routine %s failed", routine_name)
        return PostProcessingOutcome(
            routine_name=routine_name,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _as_paths(path: Path | None) -> tuple[Path, ...]:
    return (path,) if path is not None else ()


def _skipped(routine_name: str, reason: str) -> PostProcessingOutcome:
    return PostProcessingOutcome(
        routine_name=routine_name,
        status="skipped",
        skip_reason=reason,
    )


def _skip_empty_output(outcome: PostProcessingOutcome) -> PostProcessingOutcome:
    if outcome.status != "succeeded" or outcome.created_paths:
        return outcome
    return _skipped(outcome.routine_name, "no matching case output")
