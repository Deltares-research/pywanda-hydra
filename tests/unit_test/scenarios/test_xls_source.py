"""Unit tests for edge cases and error branches in scenarios/sources/xls.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.scenarios import ScenarioLoadOptions
from pywandahydra.scenarios.excel.cases import _extract_analysis_meta, _require_columns
from pywandahydra.scenarios.excel.post_processing import (
    _as_str_or_none,
    _float_or_none,
    _is_nan,
    _read_output_sheet,
    _read_rplots_sheet,
    _read_tplots_sheet,
)


class TestIsNan(unittest.TestCase):
    def test_nan_value_returns_true(self) -> None:
        self.assertTrue(_is_nan(float("nan")))

    def test_regular_value_returns_false(self) -> None:
        self.assertFalse(_is_nan(5))

    def test_unhashable_list_returns_false(self) -> None:
        # pd.isna([1, 2]) returns an array; bool() on it raises ValueError,
        # which _is_nan should swallow and report as "not NaN".
        self.assertFalse(_is_nan([1, 2]))


class TestAsStrOrNone(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_as_str_or_none(None))

    def test_nan_returns_none(self) -> None:
        self.assertIsNone(_as_str_or_none(float("nan")))

    def test_blank_string_returns_none(self) -> None:
        self.assertIsNone(_as_str_or_none("   "))

    def test_value_is_stripped(self) -> None:
        self.assertEqual(_as_str_or_none("  hi  "), "hi")


class TestFloatOrNone(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_float_or_none(None))

    def test_nan_returns_none(self) -> None:
        self.assertIsNone(_float_or_none(float("nan")))

    def test_numeric_string_returns_float(self) -> None:
        self.assertEqual(_float_or_none("1.5"), 1.5)

    def test_unparsable_value_returns_none(self) -> None:
        self.assertIsNone(_float_or_none("not-a-number"))

    def test_unparsable_type_returns_none(self) -> None:
        self.assertIsNone(_float_or_none([1, 2]))


class TestRequireColumns(unittest.TestCase):
    def test_missing_columns_raises_value_error(self) -> None:
        df = pd.DataFrame({"Number": [1], "Name": ["a"]})

        with self.assertRaises(ValueError) as ctx:
            _require_columns(df, {"Number", "Include", "Name"}, "Cases")

        self.assertIn("Include", str(ctx.exception))
        self.assertIn("Cases", str(ctx.exception))

    def test_all_present_does_not_raise(self) -> None:
        df = pd.DataFrame({"Number": [1], "Include": [True], "Name": ["a"]})

        _require_columns(df, {"Number", "Include", "Name"}, "Cases")


class TestExtractAnalysisMeta(unittest.TestCase):
    def test_extracts_metadata_from_property_row(self) -> None:
        df = pd.DataFrame(
            {
                ("Description", ""): ["My analysis"],
                ("Extra", ""): ["2024.1"],
                ("Include", ""): [42],
            }
        )
        df.columns = pd.MultiIndex.from_tuples(df.columns)

        meta = _extract_analysis_meta(df, 0, ScenarioLoadOptions())

        self.assertEqual(meta.analysis_description, "My analysis")
        self.assertEqual(meta.wanda_version, "2024.1")
        self.assertEqual(meta.project_number, 42)


class TestReadOutputSheet(unittest.TestCase):
    def _write_workbook(self, td: str, sheets: dict[str, pd.DataFrame]) -> Path:
        xlsx = Path(td) / "wb.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False, header=False)
        return xlsx

    def test_missing_sheet_returns_empty_list_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = self._write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            specs = _read_output_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(specs, [])

    def test_missing_sheet_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            xlsx = self._write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            with self.assertRaises(ValueError) as ctx:
                _read_output_sheet(xlsx, opts)

        self.assertIn("Output", str(ctx.exception))

    def test_too_few_columns_returns_empty_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame([["PIPE P1", "Head"]])
            xlsx = self._write_workbook(td, {"Output": df})

            specs = _read_output_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(specs, [])

    def test_too_few_columns_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame([["PIPE P1", "Head"]])
            xlsx = self._write_workbook(td, {"Output": df})

            with self.assertRaises(ValueError) as ctx:
                _read_output_sheet(xlsx, opts)

        self.assertIn("at least 3 columns", str(ctx.exception))

    def test_incomplete_row_skipped_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                [
                    ["PIPE P1", "Head", "MAX"],
                    ["PIPE P2", None, "MIN"],
                ]
            )
            xlsx = self._write_workbook(td, {"Output": df})

            specs = _read_output_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].component, "PIPE P1")

    def test_incomplete_row_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                [
                    ["PIPE P1", "Head", "MAX"],
                    ["PIPE P2", None, "MIN"],
                ]
            )
            xlsx = self._write_workbook(td, {"Output": df})

            with self.assertRaises(ValueError) as ctx:
                _read_output_sheet(xlsx, opts)

        self.assertIn("incomplete row", str(ctx.exception))

    def test_fully_blank_row_skipped_even_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                [
                    ["PIPE P1", "Head", "MAX"],
                    [None, None, None],
                ]
            )
            xlsx = self._write_workbook(td, {"Output": df})

            specs = _read_output_sheet(xlsx, opts)

        self.assertEqual(len(specs), 1)

    def test_duplicate_component_property_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                [
                    ["PIPE P1", "Head", "MAX"],
                    ["PIPE P1", "Head", "MIN"],
                ]
            )
            xlsx = self._write_workbook(td, {"Output": df})

            with self.assertRaises(ValueError) as ctx:
                _read_output_sheet(xlsx, opts)

        self.assertIn("duplicate", str(ctx.exception))

    def test_duplicate_component_property_kept_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                [
                    ["PIPE P1", "Head", "MAX"],
                    ["PIPE P1", "Head", "MIN"],
                ]
            )
            xlsx = self._write_workbook(td, {"Output": df})

            specs = _read_output_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 2)


class TestParsePlotSheets(unittest.TestCase):
    def _write_workbook(self, td: str, sheets: dict[str, pd.DataFrame]) -> Path:
        xlsx = Path(td) / "wb.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        return xlsx

    def test_missing_rplots_sheet_returns_empty_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = self._write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(specs, [])

    def test_missing_rplots_sheet_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            xlsx = self._write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            with self.assertRaises(ValueError) as ctx:
                _read_rplots_sheet(xlsx, opts)

        self.assertIn("Rplots", str(ctx.exception))

    def test_rplots_sheet_disabled_returns_empty(self) -> None:
        opts = ScenarioLoadOptions(rplots_sheet=None)

        specs = _read_rplots_sheet(Path("does-not-matter.xlsx"), opts)

        self.assertEqual(specs, [])

    def test_tplots_sheet_disabled_returns_empty(self) -> None:
        opts = ScenarioLoadOptions(tplots_sheet=None)

        specs = _read_tplots_sheet(Path("does-not-matter.xlsx"), opts)

        self.assertEqual(specs, [])

    def test_missing_required_columns_returns_empty_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame({"title": ["t"], "name": ["n"]})  # missing "property"
            xlsx = self._write_workbook(td, {"Rplots": df})

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(specs, [])

    def test_missing_required_columns_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame({"title": ["t"], "name": ["n"]})  # missing "property"
            xlsx = self._write_workbook(td, {"Rplots": df})

            with self.assertRaises(ValueError) as ctx:
                _read_rplots_sheet(xlsx, opts)

        self.assertIn("missing required column", str(ctx.exception))

    def test_incomplete_row_skipped_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                {
                    "title": ["Route A", "Route B"],
                    "name": ["Route_A", None],
                    "property": ["Head", "Pressure"],
                }
            )
            xlsx = self._write_workbook(td, {"Rplots": df})

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].route_id, "Route_A")

    def test_incomplete_row_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                {
                    "title": ["Route A", "Route B"],
                    "name": ["Route_A", None],
                    "property": ["Head", "Pressure"],
                }
            )
            xlsx = self._write_workbook(td, {"Rplots": df})

            with self.assertRaises(ValueError) as ctx:
                _read_rplots_sheet(xlsx, opts)

        self.assertIn("incomplete row", str(ctx.exception))

    def test_fully_blank_row_skipped_even_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                {
                    "title": ["Route A", None],
                    "name": ["Route_A", None],
                    "property": ["Head", None],
                }
            )
            xlsx = self._write_workbook(td, {"Rplots": df})

            specs = _read_rplots_sheet(xlsx, opts)

        self.assertEqual(len(specs), 1)

    def test_duplicate_title_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                {
                    "title": ["Route A", "Route A"],
                    "name": ["Route_A", "Route_B"],
                    "property": ["Head", "Pressure"],
                }
            )
            xlsx = self._write_workbook(td, {"Rplots": df})

            with self.assertRaises(ValueError) as ctx:
                _read_rplots_sheet(xlsx, opts)

        self.assertIn("duplicate route title", str(ctx.exception))

    def test_duplicate_title_kept_when_not_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            df = pd.DataFrame(
                {
                    "title": ["Route A", "Route A"],
                    "name": ["Route_A", "Route_B"],
                    "property": ["Head", "Pressure"],
                }
            )
            xlsx = self._write_workbook(td, {"Rplots": df})

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 2)

    def test_missing_tplots_sheet_raises_when_strict(self) -> None:
        opts = ScenarioLoadOptions(strict_validation=True)
        with tempfile.TemporaryDirectory() as td:
            xlsx = self._write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            with self.assertRaises(ValueError) as ctx:
                _read_tplots_sheet(xlsx, opts)

        self.assertIn("Tplots", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
