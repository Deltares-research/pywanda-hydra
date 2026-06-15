"""Unit tests for postprocessing.reports.tables."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.reports.tables import (
    aggregate_case_tables,
    render_summary_table,
)
from pywandahydra.scenarios.schema import ExportTableSpecification


class TestRenderSummaryTable(unittest.TestCase):
    def test_empty_cache_returns_empty_dataframe_with_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            specs = [ExportTableSpecification(component="PUMP P1", property="Head", mode="MAX")]

            result = render_summary_table(specs, cache)

            self.assertTrue(result.empty)
            self.assertEqual(list(result.columns), ["component", "property", "mode", "value"])

    def test_multiindex_columns_max_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            columns = pd.MultiIndex.from_tuples(
                [("PUMP P1", "Head", float("nan")), ("PIPE P1", "Pressure", 10.0)],
                names=["component", "property", "s_location"],
            )
            components = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns, index=[0.0, 1.0])
            cache.write({"components": components, "routes": {}})

            specs = [ExportTableSpecification(component="PUMP P1", property="Head", mode="MAX")]

            result = render_summary_table(specs, cache)

            self.assertEqual(len(result), 1)
            row = result.iloc[0]
            self.assertEqual(row["component"], "PUMP P1")
            self.assertEqual(row["property"], "Head")
            self.assertEqual(row["mode"], "MAX")
            self.assertEqual(row["value"], 3.0)

    def test_multiindex_columns_min_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            columns = pd.MultiIndex.from_tuples(
                [("PUMP P1", "Head", float("nan"))],
                names=["component", "property", "s_location"],
            )
            components = pd.DataFrame([[1.0], [3.0]], columns=columns, index=[0.0, 1.0])
            cache.write({"components": components, "routes": {}})

            specs = [ExportTableSpecification(component="PUMP P1", property="Head", mode="MIN")]

            result = render_summary_table(specs, cache)

            self.assertEqual(result.iloc[0]["value"], 1.0)

    def test_multiindex_no_matching_columns_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            columns = pd.MultiIndex.from_tuples(
                [("PUMP P1", "Head", float("nan"))],
                names=["component", "property", "s_location"],
            )
            components = pd.DataFrame([[1.0], [3.0]], columns=columns, index=[0.0, 1.0])
            cache.write({"components": components, "routes": {}})

            specs = [ExportTableSpecification(component="MISSING", property="Flow", mode="MAX")]

            result = render_summary_table(specs, cache)

            self.assertTrue(result.empty)

    def test_output_dir_saves_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cache_dir = tmp_path / "cache"
            output_dir = tmp_path / "out"

            cache = ParquetCache(cache_dir)
            columns = pd.MultiIndex.from_tuples(
                [("PUMP P1", "Head", float("nan"))],
                names=["component", "property", "s_location"],
            )
            components = pd.DataFrame([[1.0], [3.0]], columns=columns, index=[0.0, 1.0])
            cache.write({"components": components, "routes": {}})

            specs = [ExportTableSpecification(component="PUMP P1", property="Head", mode="MAX")]

            result = render_summary_table(specs, cache, output_dir=output_dir)

            self.assertFalse(result.empty)
            saved_files = list(output_dir.glob("summary_table*"))
            self.assertTrue(saved_files)


class TestAggregateCaseTables(unittest.TestCase):
    def test_no_case_tables_returns_empty_dataframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"
            scenarios_dir.mkdir()
            output_dir = Path(tmp_dir) / "out"

            result = aggregate_case_tables(scenarios_dir, output_dir, run_id="run1")

            self.assertTrue(result.empty)
            self.assertEqual(
                list(result.columns), ["case", "component", "property", "mode", "value"]
            )

    def test_aggregates_per_case_csv_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"
            scenarios_dir.mkdir()
            output_dir = Path(tmp_dir) / "out"

            case_dir = scenarios_dir / "case_001"
            case_dir.mkdir()
            df = pd.DataFrame(
                {
                    "component": ["PUMP P1"],
                    "property": ["Head"],
                    "mode": ["MAX"],
                    "value": [1.0],
                }
            )
            df.to_csv(case_dir / "summary_table.csv", index=False)

            # A directory entry with no summary_table.csv should be skipped.
            empty_case_dir = scenarios_dir / "case_002"
            empty_case_dir.mkdir()

            # A non-directory entry should be skipped.
            (scenarios_dir / "not_a_dir.txt").write_text("hello")

            result = aggregate_case_tables(scenarios_dir, output_dir, run_id="run1")

            self.assertEqual(len(result), 1)
            self.assertEqual(result.iloc[0]["case"], "case_001")
            saved_files = list(output_dir.glob("aggregated_table_run1*"))
            self.assertTrue(saved_files)


if __name__ == "__main__":
    unittest.main()
