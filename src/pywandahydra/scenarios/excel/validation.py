"""Excel workbook structural validation and strict warning promotion."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from ..models.document import ScenarioWarning

if TYPE_CHECKING:
    from ..loader import ScenarioLoadOptions


class ScenarioValidationError(ValueError):
    """Collected scenario-document validation issues."""

    def __init__(
        self,
        warnings: list[ScenarioWarning],
        *,
        context: str = "scenario document",
    ) -> None:
        self.warnings = tuple(warnings)
        lines = [f"{context} has {len(warnings)} validation issue(s):"]
        for issue in warnings:
            location = f"[{issue.sheet}]"
            if issue.row is not None:
                location += f" row={issue.row}"
            if issue.column is not None:
                location += f" column={issue.column}"
            lines.append(f"- {location} {issue.message}")
        super().__init__("\n".join(lines))


def _add_warning(
    warnings_list: list[ScenarioWarning],
    *,
    sheet: str,
    message: str,
    row: int | None = None,
    column: str | None = None,
    expected_shape: str | None = None,
) -> None:
    warnings_list.append(
        ScenarioWarning(
            sheet=sheet,
            message=message,
            row=row,
            column=column,
            expected_shape=expected_shape,
        )
    )


def check_xls_structure(path: str | Path, opts: ScenarioLoadOptions) -> list[ScenarioWarning]:
    issues: list[ScenarioWarning] = []

    try:
        book_ctx = pd.ExcelFile(path)
    except Exception as exc:
        _add_warning(
            issues,
            sheet="<workbook>",
            message=f"Could not open workbook: {exc}",
            expected_shape="Readable xls/xlsx/xlsm workbook",
        )
        return issues

    with book_ctx as book:
        sheet_names = set(book.sheet_names)

        if opts.cases_sheet not in sheet_names:
            _add_warning(
                issues,
                sheet=opts.cases_sheet,
                message=(
                    f"Required sheet '{opts.cases_sheet}' not found. "
                    f"Available sheets: {sorted(sheet_names)}"
                ),
                expected_shape="Cases sheet with Number/Include/Name columns",
            )
        else:
            header = pd.read_excel(book, opts.cases_sheet, header=None, nrows=1).values[0]
            header_set = {str(h).strip() for h in header}
            missing = {"Number", "Include", "Name"} - header_set
            if missing:
                _add_warning(
                    issues,
                    sheet=opts.cases_sheet,
                    message=f"Missing required column(s): {sorted(missing)}",
                    expected_shape="Cases columns include Number, Include, Name",
                )

        plot_sheets: tuple[tuple[str | None, str], ...] = (
            (opts.rplots_sheet, "RPlots"),
            (opts.tplots_sheet, "TPlots"),
        )
        for sheet_name, kind in plot_sheets:
            if sheet_name is None:
                continue
            if sheet_name not in sheet_names:
                _add_warning(
                    issues,
                    sheet=sheet_name,
                    message=(
                        f"Sheet '{sheet_name}' not found (required because "
                        f"{kind.lower()}_sheet is configured). "
                        f"Available sheets: {sorted(sheet_names)}"
                    ),
                    expected_shape=f"{sheet_name} sheet with title/name/property columns",
                )
                continue
            columns_ci = {
                str(c).strip().lower() for c in pd.read_excel(book, sheet_name, nrows=0).columns
            }
            missing = {"title", "name", "property"} - columns_ci
            if missing:
                _add_warning(
                    issues,
                    sheet=sheet_name,
                    message=f"Missing required column(s): {sorted(missing)}",
                    expected_shape="Columns include title, name, property",
                )

        if opts.output_sheet is not None:
            if opts.output_sheet not in sheet_names:
                _add_warning(
                    issues,
                    sheet=opts.output_sheet,
                    message=(
                        f"Sheet '{opts.output_sheet}' not found (required because "
                        "output_sheet is configured). "
                        f"Available sheets: {sorted(sheet_names)}"
                    ),
                    expected_shape="Output sheet with component/property/mode columns",
                )
            else:
                n_cols = pd.read_excel(book, opts.output_sheet, header=None, nrows=1).shape[1]
                if n_cols < 3:
                    _add_warning(
                        issues,
                        sheet=opts.output_sheet,
                        message=(
                            "Sheet must have at least 3 columns (component, property, mode); "
                            f"found {n_cols}."
                        ),
                        expected_shape="At least 3 Output columns",
                    )

    return issues


def raise_if_warnings(warnings_list: list[ScenarioWarning], *, strict: bool, context: str) -> None:
    if strict and warnings_list:
        raise ScenarioValidationError(warnings_list, context=context)
