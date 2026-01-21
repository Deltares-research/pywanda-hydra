"""Module for reading scenario specifications from Excel files."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

import numpy as np
import pandas as pd
from pydantic import ValidationError

from ..schema import AnalysisMeta, ParameterChange, ScenarioMeta, ScenarioSpecification

if TYPE_CHECKING:
    from ..mapper import ScenarioLoadOptions


# Helper functions
def _is_nan(x: Any) -> bool:
    """Check if a value is NaN (Not a Number).

    Parameters
    ----------
    x : Any
        The value to check.

    Returns
    -------
    bool
        True if the value is NaN, False otherwise.
    """
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _as_str_or_none(x: Any) -> str | None:
    """Convert a value to a stripped string or None if it is NaN or empty.

    Parameters
    ----------
    x : Any
        The value to convert.

    Returns
    -------
    str | None
        The stripped string or None.
    """
    if _is_nan(x) or x is None:
        return None
    s = str(x).strip()
    return s or None


def _require_columns(df: pd.DataFrame, required: set[str], sheet: str) -> None:
    """Ensure that the DataFrame contains the required columns.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to check.
    required : set[str]
        The set of required column names.
    sheet : str
        The name of the sheet (for error messages).

    Returns
    -------
    None
        Raises ValueError if any required columns are missing.
    """
    missing = required - set(df.columns.get_level_values(0))
    if missing:
        raise ValueError(f"Missing required columns in '{sheet}': {sorted(missing)}")


def _extract_analysis_meta(
    input_data: pd.DataFrame, prop_row: int, opts: ScenarioLoadOptions
) -> AnalysisMeta:
    """Extract analysis-level metadata from the property row.

    Parameters
    ----------
    input_data : pd.DataFrame
        The input DataFrame containing scenario data.
    prop_row : int
        The index of the property row.
    opts : ScenarioLoadOptions
        The scenario load options.

    Returns
    -------
    AnalysisMeta
        The extracted analysis-level metadata.
    """

    def get_cell(col: str) -> Any:
        # Find the full column tuple where the first level matches col
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
            return input_data.loc[:, (col, "")].iloc[prop_row, 0]  # type: ignore

    return AnalysisMeta(
        analysis_description=_as_str_or_none(get_cell(opts.global_description_col)),
        wanda_version=_as_str_or_none(get_cell(opts.global_wanda_version_col)),
        project_number=get_cell(opts.global_project_number_col),
    )


def read_scenarios_from_excel(
    path: str | Path, opts: ScenarioLoadOptions
) -> List[ScenarioSpecification]:
    """Read scenarios from an Excel file.

    Parameters
    ----------
    path : str | Path
        The path to the Excel file.
    opts : ScenarioLoadOptions
        Options for loading scenarios from Excel.

    Returns
    -------
    List[ScenarioSpecification]
        A list of scenario specifications read from the Excel file.
    """
    # Read the Excel file
    input_data = pd.read_excel(
        path, opts.cases_sheet, header=None, skiprows=opts.cases_header_row_count
    )
    # Extract parameter columns
    input_headers = pd.read_excel(path, opts.cases_sheet, header=None, nrows=1).values[0]
    column_start = np.where(input_headers == "Name")[0][0] + 1
    param_columns = list(input_data.iloc[0, column_start:])

    # - Create a MultiIndex column names for the (Component, Property) pairs
    comp_prop: List[tuple[str, str]] = []

    for component, prop_name in zip(input_headers[column_start:], param_columns):
        component_str = str(component).strip()
        prop_str = str(prop_name).strip()
        comp_prop.append((component_str, prop_str))

    # -- Append initial non-parameter columns
    for col in input_headers[:column_start]:
        comp_prop.insert(len(comp_prop) - len(param_columns), (str(col).strip(), ""))

    input_data.columns = pd.MultiIndex.from_tuples(comp_prop)

    # Ensure required columns are present
    _require_columns(input_data, {"Number", "Include", "Name"}, opts.cases_sheet)

    # Index of the property row
    prop_row = opts.cases_property_row_index

    # Extract analysis-level metadata
    analysis_context = _extract_analysis_meta(input_data, prop_row, opts)

    # Construct scenarios
    scenarios: List[ScenarioSpecification] = []
    for i in range(prop_row + 1, len(input_data)):
        # Access Number column using the MultiIndex tuple ("Number", "")
        number_col = ("Number", "")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
            if _is_nan(input_data.iloc[i, :][number_col].values[0]):
                continue

        # Extract metadata
        row_dict = input_data.iloc[i].to_dict()
        try:
            # For meta fields, extract only the first level of the MultiIndex
            meta_df = {k[0]: v for k, v in row_dict.items() if k[1] == ""}
            meta = ScenarioMeta.model_validate(meta_df)
        except ValidationError as e:
            raise ValueError(
                f"Error validating scenario metadata at row {i} in '{opts.cases_sheet}': {e}"
            ) from e

        # Extract parameter changes
        parameters: List[ParameterChange] = []
        for col_tuple in input_data.columns:
            prop_name = col_tuple[1]
            if prop_name == "":
                continue  # Skip non-parameter columns

            # Get value and check for NaN
            value = row_dict[col_tuple]
            if opts.nan_means_skip_parameter and _is_nan(value):
                continue

            # Add parameter change
            parameters.append(
                ParameterChange(
                    component=col_tuple[0],
                    property=prop_name,
                    value=value,
                )
            )

        # Construct ScenarioSpecification only if included
        if not meta.include:
            print(f"Scenario '{meta.name}' (Number={meta.number}) is not included.")
            continue

        scenarios.append(
            ScenarioSpecification(
                meta=meta,
                parameters=parameters,
                analysis_meta=analysis_context,
                source={
                    "file": path,
                    "sheet": opts.cases_sheet,
                    "row_index": i,
                },
            )
        )

    return scenarios
