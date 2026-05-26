"""Module for reading scenario specifications from Excel files."""

from __future__ import annotations

import logging
import warnings

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, cast

import numpy as np
import pandas as pd
from pydantic import ValidationError

from pywandahydra.postprocessing.plotting.specifications import AxisSpec

from ..schema import (
    AnalysisMeta,
    ExportTableSpecification,
    ParameterChange,
    RoutePlotSpecification,
    ScenarioMeta,
    ScenarioSpecification,
)

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
            return input_data.loc[:, (col, "")].values[prop_row]

    return AnalysisMeta(
        analysis_description=_as_str_or_none(get_cell(opts.global_description_col)),
        wanda_version=_as_str_or_none(get_cell(opts.global_wanda_version_col)),
        project_number=get_cell(opts.global_project_number_col),
    )


def _read_output_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
) -> List[ExportTableSpecification]:
    """Read the *Output* sheet and return a list of export-table specifications.

    Expected sheet layout (no header row, columns by position)::

        PIPE P1   | Head     | MAX
        PIPE P2   | Pressure | MIN

    Column 0 = component, column 1 = property, column 2 = mode.

    The sheet is silently skipped (returns ``[]``) when it does not exist.

    Parameters
    ----------
    path : str | Path
        The path to the Excel file.
    opts : ScenarioLoadOptions
        Scenario load options (provides sheet name).

    Returns
    -------
    List[ExportTableSpecification]
        Parsed export-table specifications.
    """
    try:
        df = cast(pd.DataFrame, pd.read_excel(path, opts.output_sheet, header=None))
    except ValueError:
        # Sheet does not exist
        return []

    # Skip if there are fewer than 3 columns (component, property, mode)
    if df.shape[1] < 3:
        return []

    specs: List[ExportTableSpecification] = []
    for _, row in df.iterrows():
        comp = _as_str_or_none(row.iloc[0])
        prop = _as_str_or_none(row.iloc[1])
        mode_str = _as_str_or_none(row.iloc[2])

        if comp is None or prop is None or mode_str is None:
            continue

        mode = cast(Any, mode_str)
        specs.append(ExportTableSpecification(component=comp, property=prop, mode=mode))

    return specs


def _read_rplots_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
) -> List[RoutePlotSpecification]:
    """Read the *RPlots* sheet and return a list of route-plot specifications.

    Expected sheet layout (with a header row)::

        title | Legend | Xlabel | Ylabel | Xmin | Xtick
        Xmax  | Xscale | Ymin  | Ytick  | Ymax | Yscale

    The sheet is silently skipped (returns ``[]``) when it does not exist.

    Parameters
    ----------
    path : str | Path
        The path to the Excel file.
    opts : ScenarioLoadOptions
        Scenario load options (provides sheet name).

    Returns
    -------
    List[RoutePlotSpecification]
        Parsed route-plot specifications.
    """
    try:
        df = cast(pd.DataFrame, pd.read_excel(path, opts.rplots_sheet))
    except ValueError:
        # Sheet does not exist
        return []

    if "title" not in df.columns:
        return []

    def _float_or_none(val: Any) -> float | None:
        if _is_nan(val) or val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    specs: List[RoutePlotSpecification] = []
    for _, row in df.iterrows():
        comp = _as_str_or_none(row.get("component"))
        prop = _as_str_or_none(row.get("property"))

        if comp is None or prop is None:
            continue

        title = _as_str_or_none(row.get("title"))

        x_axis = AxisSpec(
            label=_as_str_or_none(row.get("Xlabel")) or "",
            min=_float_or_none(row.get("Xmin")),
            max=_float_or_none(row.get("Xmax")),
            tick_interval=_float_or_none(row.get("Xtick")),
            factor=_float_or_none(row.get("Xscale")) or 1.0,
        )
        y_axis = AxisSpec(
            label=_as_str_or_none(row.get("Ylabel")) or "",
            min=_float_or_none(row.get("Ymin")),
            max=_float_or_none(row.get("Ymax")),
            tick_interval=_float_or_none(row.get("Ytick")),
            factor=_float_or_none(row.get("Yscale")) or 1.0,
        )

        specs.append(
            RoutePlotSpecification(
                route_id=comp or "",
                property=prop or "",
                title=title,
                legend=_as_str_or_none(row.get("Legend")),
                x_axis=x_axis,
                y_axis=y_axis,
            )
        )

    return specs


def read_scenarios_from_excel(
    path: str | Path, opts: ScenarioLoadOptions
) -> List[ScenarioSpecification]:
    """Read scenarios from an Excel file.

    Reads the *Cases* sheet for scenario parameters, and optionally the
    *Output* and *RPlots* sheets for post-processing specifications.

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

    # Load post-processing specifications from optional sheets
    output_specs = _read_output_sheet(path, opts) if opts.output_sheet else []
    rplot_specs = _read_rplots_sheet(path, opts) if opts.rplots_sheet else []

    # Construct scenarios
    scenarios: List[ScenarioSpecification] = []
    for i in range(prop_row + 1, len(input_data)):
        # Access Number column using the MultiIndex tuple ("Number", "")
        number_col = ("Number", "")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
            if _is_nan(input_data.iloc[i, :][number_col]):
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
            logger.debug("Scenario '%s' (Number=%d) is not included.", meta.name, meta.number)
            continue

        scenarios.append(
            ScenarioSpecification(
                meta=meta,
                parameters=parameters,
                outputs=output_specs,
                route_plots=rplot_specs,
                analysis_meta=analysis_context,
                source={
                    "file": path,
                    "sheet": opts.cases_sheet,
                    "row_index": i,
                },
            )
        )

    return scenarios
