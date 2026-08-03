"""Excel Cases-sheet parsing."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from pydantic import ValidationError

from ..models.document import ScenarioWarning
from ..models.meta import AnalysisMeta
from ..models.parameter_change import ModelParameterChange
from ..models.report import ReportConfiguration
from .post_processing import _as_str_or_none, _is_nan

if TYPE_CHECKING:
    from ..loader import ScenarioLoadOptions


@dataclass(frozen=True, slots=True)
class ParsedCaseRow:
    number: Any
    include: Any
    name: Any
    parameter_changes: list[ModelParameterChange]
    report: ReportConfiguration
    extra_columns: dict[str, Any]
    source: dict[str, Any]


def _require_columns(df: pd.DataFrame, required: set[str], sheet: str) -> None:
    missing = required - set(df.columns.get_level_values(0))
    if missing:
        raise ValueError(f"Missing required columns in '{sheet}': {sorted(missing)}")


def _extract_analysis_meta(
    input_data: pd.DataFrame, prop_row: int, opts: ScenarioLoadOptions
) -> AnalysisMeta:
    def get_cell(col: str) -> Any:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
            value = input_data.loc[:, (col, "")].values[prop_row]
        if isinstance(value, np.ndarray) and value.size == 1:
            return value.item()
        return value

    return AnalysisMeta(
        analysis_description=_as_str_or_none(get_cell(opts.global_description_col)),
        wanda_version=_as_str_or_none(get_cell(opts.global_wanda_version_col)),
        project_number=get_cell(opts.global_project_number_col),
    )


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


def parse_cases_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
) -> tuple[AnalysisMeta, list[ParsedCaseRow], list[ScenarioWarning]]:
    input_data = pd.read_excel(
        path,
        opts.cases_sheet,
        header=None,
        skiprows=opts.cases_header_row_count,
    )
    input_headers = pd.read_excel(path, opts.cases_sheet, header=None, nrows=1).values[0]
    column_start = np.where(input_headers == "Name")[0][0] + 1
    param_columns = list(input_data.iloc[0, column_start:])

    comp_prop: list[tuple[str, str]] = []
    for component, prop_name in zip(input_headers[column_start:], param_columns, strict=False):
        comp_prop.append((str(component).strip(), str(prop_name).strip()))

    for col in input_headers[:column_start]:
        comp_prop.insert(len(comp_prop) - len(param_columns), (str(col).strip(), ""))

    input_data.columns = pd.MultiIndex.from_tuples(comp_prop)
    _require_columns(input_data, {"Number", "Include", "Name"}, opts.cases_sheet)

    prop_row = opts.cases_property_row_index
    analysis_meta = _extract_analysis_meta(input_data, prop_row, opts)

    warnings_list: list[ScenarioWarning] = []
    rows: list[ParsedCaseRow] = []
    number_col = ("Number", "")
    number_col_pos = list(input_data.columns).index(number_col)

    for i in range(prop_row + 1, len(input_data)):
        number_value = input_data.iloc[i, number_col_pos]
        if _is_nan(number_value):
            continue

        row_dict = input_data.iloc[i].to_dict()
        meta_df: dict[str, Any] = {}
        for k, v in row_dict.items():
            if k[1] != "":
                continue
            if _is_nan(v):
                meta_df[k[0]] = None
            elif isinstance(v, np.generic):
                meta_df[k[0]] = v.item()
            else:
                meta_df[k[0]] = v

        identity_keys = {"Number", "Include", "Name"}
        report_keys = {"Description", "Appendix", "Chapter", "Date"}
        extra_columns = {
            key: value
            for key, value in meta_df.items()
            if key not in identity_keys and key not in report_keys
        }

        try:
            report = ReportConfiguration(
                description=meta_df.get("Description"),
                appendix=meta_df.get("Appendix"),
                chapter=meta_df.get("Chapter"),
                date=meta_df.get("Date"),
            )
        except ValidationError as exc:
            _add_warning(
                warnings_list,
                sheet=opts.cases_sheet,
                row=i,
                message=f"Invalid report metadata: {exc}",
                expected_shape="Description/Appendix/Chapter/Date values compatible with schema",
            )
            report = ReportConfiguration()

        parameter_changes: list[ModelParameterChange] = []
        for col_tuple in input_data.columns:
            prop_name = col_tuple[1]
            if prop_name == "":
                continue

            value = row_dict[col_tuple]
            if opts.nan_means_skip_parameter and _is_nan(value):
                continue

            if isinstance(value, np.generic):
                value = value.item()

            try:
                parameter_changes.append(
                    ModelParameterChange(component=col_tuple[0], property=prop_name, value=value)
                )
            except ValidationError as exc:
                _add_warning(
                    warnings_list,
                    sheet=opts.cases_sheet,
                    row=i,
                    column=f"{col_tuple[0]}.{prop_name}",
                    message=f"Invalid parameter change: {exc}",
                    expected_shape="Parameter cells should map to ModelParameterChange",
                )

        rows.append(
            ParsedCaseRow(
                number=meta_df.get("Number"),
                include=meta_df.get("Include", True),
                name=meta_df.get("Name"),
                parameter_changes=parameter_changes,
                report=report,
                extra_columns=extra_columns,
                source={"file": path, "sheet": opts.cases_sheet, "row_index": i},
            )
        )

    return analysis_meta, rows, warnings_list
