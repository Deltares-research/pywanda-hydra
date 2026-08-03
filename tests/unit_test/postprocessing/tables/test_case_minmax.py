"""Unit tests for per-case MIN/MAX table calculation."""

from __future__ import annotations

import pandas as pd

from pywandahydra.postprocessing.tables.case_minmax import calculate_case_minmax_table
from pywandahydra.scenarios import MinMaxTableSpecification


def test_calculate_case_minmax_table_has_no_filesystem_dependency() -> None:
    columns = pd.MultiIndex.from_tuples(
        [("PUMP P1", "Head", float("nan")), ("PIPE P1", "Pressure", 10.0)],
        names=["component", "property", "s_location"],
    )
    components = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns)

    result = calculate_case_minmax_table(
        [
            MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX"),
            MinMaxTableSpecification(component="PIPE P1", property="Pressure", mode="MIN"),
        ],
        components,
    )

    assert result.to_dict("records") == [
        {"component": "PUMP P1", "property": "Head", "mode": "MAX", "value": 3.0},
        {"component": "PIPE P1", "property": "Pressure", "mode": "MIN", "value": 2.0},
    ]


def test_calculate_case_minmax_table_supports_flat_columns_and_missing_properties() -> None:
    components = pd.DataFrame({"PUMP P1|Head": [3.0, 1.0]})

    result = calculate_case_minmax_table(
        [
            MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MIN"),
            MinMaxTableSpecification(component="MISSING", property="Flow", mode="MAX"),
        ],
        components,
    )

    assert result.to_dict("records") == [
        {"component": "PUMP P1", "property": "Head", "mode": "MIN", "value": 1.0}
    ]


def test_calculate_case_minmax_table_returns_empty_table_for_empty_components() -> None:
    result = calculate_case_minmax_table([], pd.DataFrame())

    assert result.empty
    assert list(result.columns) == ["component", "property", "mode", "value"]
