"""Excel workbook orchestration into ScenarioDocument."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ..models.document import ScenarioDocument, ScenarioWarning
from ..models.post_processing import (
    FigurePostProcessingConfiguration,
    PostProcessingConfiguration,
    TablePostProcessingConfiguration,
)
from ..models.scenario import ScenarioSpecification
from .cases import parse_cases_sheet
from .post_processing import _read_output_sheet, _read_rplots_sheet, _read_tplots_sheet
from .validation import raise_if_warnings

if TYPE_CHECKING:
    from ..loader import ScenarioLoadOptions


def load_excel_document(
    path: str | Path,
    opts: ScenarioLoadOptions,
    *,
    strict: bool = False,
) -> ScenarioDocument:
    """Load a workbook into a ``ScenarioDocument`` using the Excel parsers.

    The cases sheet and optional post-processing sheets are parsed once, warnings
    are accumulated, and strict mode can promote those warnings to a single
    ``ScenarioValidationError``.

    Parameters
    ----------
    path:
        Workbook path.
    opts:
        Scenario loading options (sheet names, row semantics, strict defaults).
    strict:
        When ``True``, collected parser warnings are raised as a single error.

    Returns
    -------
    ScenarioDocument
        Parsed workbook aggregate with metadata, scenarios, source path, and
        typed warnings.
    """
    analysis_metadata, case_rows, case_warnings = parse_cases_sheet(path, opts)

    parser_warnings: list[ScenarioWarning] = list(case_warnings)
    output_specs = _read_output_sheet(path, opts, warnings_list=parser_warnings)
    rplot_specs = _read_rplots_sheet(path, opts, warnings_list=parser_warnings)
    tplot_specs = _read_tplots_sheet(path, opts, warnings_list=parser_warnings)

    scenarios: list[ScenarioSpecification] = []
    for row in case_rows:
        try:
            scenarios.append(
                ScenarioSpecification(
                    number=row.number,
                    include=row.include,
                    name=row.name,
                    parameter_changes=row.parameter_changes,
                    post_processing=PostProcessingConfiguration(
                        tables=TablePostProcessingConfiguration(minmax=output_specs),
                        figures=FigurePostProcessingConfiguration(
                            routes=rplot_specs,
                            time_series=tplot_specs,
                        ),
                        report=row.report,
                    ),
                    extra_columns=row.extra_columns,
                    source=row.source,
                )
            )
        except ValidationError as exc:
            parser_warnings.append(
                ScenarioWarning(
                    sheet=opts.cases_sheet,
                    row=row.source.get("row_index"),
                    message=f"Invalid scenario row: {exc}",
                    expected_shape="Cases rows must satisfy ScenarioSpecification",
                )
            )

    raise_if_warnings(parser_warnings, strict=strict, context="excel scenario parsing")

    return ScenarioDocument(
        analysis_metadata=analysis_metadata,
        scenarios=tuple(scenarios),
        source_path=Path(path),
        warnings=tuple(parser_warnings),
    )
