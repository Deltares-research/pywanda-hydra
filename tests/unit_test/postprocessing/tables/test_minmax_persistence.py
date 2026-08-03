"""Unit tests for MIN/MAX table persistence."""

from __future__ import annotations

import pandas as pd

from pywandahydra.postprocessing.tables.case_minmax import write_case_minmax_table
from pywandahydra.postprocessing.tables.run_minmax import (
    combine_case_minmax_tables,
    write_run_minmax_table,
)
from pywandahydra.results import ComponentTimeSeries, ExtractedSimulationData, ParquetResultStore
from pywandahydra.scenarios import MinMaxTableSpecification


def test_write_case_minmax_table_persists_calculated_table(tmp_path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    columns = pd.MultiIndex.from_tuples(
        [("PUMP P1", "Head", float("nan"))],
        names=["component", "property", "s_location"],
    )
    store.write(
        ExtractedSimulationData(
            components=ComponentTimeSeries(pd.DataFrame([[1.0], [3.0]], columns=columns))
        ),
        fingerprint="test",
    )

    paths = write_case_minmax_table(
        [MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")],
        store,
        tmp_path / "tables",
    )

    assert paths == (tmp_path / "tables" / "summary_table.csv",)
    assert pd.read_csv(paths[0]).to_dict("records") == [
        {"component": "PUMP P1", "property": "Head", "mode": "MAX", "value": 3.0}
    ]


def test_write_case_minmax_table_returns_no_paths_for_missing_data(tmp_path) -> None:
    paths = write_case_minmax_table(
        [MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")],
        ParquetResultStore(tmp_path / "results"),
        tmp_path / "tables",
    )

    assert paths == ()


def test_combine_case_minmax_tables_orders_case_names_deterministically() -> None:
    table = pd.DataFrame(
        [{"component": "PUMP P1", "property": "Head", "mode": "MAX", "value": 1.0}]
    )

    result = combine_case_minmax_tables({"case_002": table, "case_001": table})

    assert result["case"].to_list() == ["case_001", "case_002"]


def test_write_run_minmax_table_skips_missing_case_inputs(tmp_path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "case_002").mkdir()
    case_dir = scenarios_dir / "case_001"
    case_dir.mkdir()
    pd.DataFrame(
        [{"component": "PUMP P1", "property": "Head", "mode": "MAX", "value": 1.0}]
    ).to_csv(case_dir / "summary_table.csv", index=False)

    paths = write_run_minmax_table(scenarios_dir, tmp_path / "tables", "run1")

    assert paths == (tmp_path / "tables" / "aggregated_table_run1.csv",)
    assert pd.read_csv(paths[0])["case"].to_list() == ["case_001"]


def test_write_run_minmax_table_returns_no_paths_without_case_tables(tmp_path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()

    assert write_run_minmax_table(scenarios_dir, tmp_path / "tables", "run1") == ()
