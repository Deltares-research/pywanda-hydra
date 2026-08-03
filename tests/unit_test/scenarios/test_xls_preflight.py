"""Unit tests for structural preflight checks in scenarios/sources/xls.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.scenarios import (
    ScenarioLoadOptions,
    assert_scenario_file_valid,
    check_scenario_file,
)
from pywandahydra.scenarios.excel.validation import check_xls_structure

_VALID_CASES = pd.DataFrame(
    [
        ["Number", "Include", "Name", "Description", "Extra", "PIPE P1"],
        [None, None, None, None, None, "Diameter"],
        [1, True, "Case 1", "desc", "2024.1", 0.5],
    ]
)
_VALID_RPLOTS = pd.DataFrame({"title": ["t1"], "name": ["R1"], "property": ["Head"]})
_VALID_TPLOTS = pd.DataFrame({"title": ["t1"], "name": ["PIPE P1"], "property": ["Head"]})
_VALID_OUTPUT = pd.DataFrame([["PIPE P1", "Head", "MAX"]])


def _write_workbook(td: str, sheets: dict[str, pd.DataFrame], *, header: bool = True) -> Path:
    xlsx = Path(td) / "wb.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False, header=header)
    return xlsx


class TestCheckXlsStructure(unittest.TestCase):
    def test_all_sheets_valid_returns_no_issues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = Path(td) / "wb.xlsx"
            # Cases/Output have no header row; Rplots/Tplots do.
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                _VALID_CASES.to_excel(writer, sheet_name="Cases", index=False, header=False)
                _VALID_RPLOTS.to_excel(writer, sheet_name="Rplots", index=False, header=True)
                _VALID_TPLOTS.to_excel(writer, sheet_name="Tplots", index=False, header=True)
                _VALID_OUTPUT.to_excel(writer, sheet_name="Output", index=False, header=False)

            issues = check_xls_structure(xlsx, ScenarioLoadOptions())

        self.assertEqual(issues, [])

    def test_missing_cases_sheet(self) -> None:
        opts = ScenarioLoadOptions(rplots_sheet=None, tplots_sheet=None, output_sheet=None)
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            issues = check_xls_structure(xlsx, opts)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].sheet, "Cases")
        self.assertIn("not found", issues[0].message)
        self.assertIn("Other", issues[0].message)

    def test_cases_sheet_missing_required_columns(self) -> None:
        bad_cases = pd.DataFrame([["Number", "Name"], [1, "Case 1"]])
        opts = ScenarioLoadOptions(rplots_sheet=None, tplots_sheet=None, output_sheet=None)
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Cases": bad_cases}, header=False)

            issues = check_xls_structure(xlsx, opts)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].sheet, "Cases")
        self.assertIn("Include", issues[0].message)

    def test_missing_rplots_sheet_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Cases": _VALID_CASES}, header=False)

            issues = check_xls_structure(xlsx, ScenarioLoadOptions())

        sheets = {issue.sheet for issue in issues}
        self.assertIn("Rplots", sheets)

    def test_rplots_sheet_disabled_skips_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Cases": _VALID_CASES}, header=False)

            issues = check_xls_structure(
                xlsx, ScenarioLoadOptions(rplots_sheet=None, tplots_sheet=None, output_sheet=None)
            )

        self.assertEqual(issues, [])

    def test_rplots_sheet_missing_required_columns(self) -> None:
        bad_rplots = pd.DataFrame({"title": ["t1"], "name": ["R1"]})
        with tempfile.TemporaryDirectory() as td:
            xlsx = Path(td) / "wb.xlsx"
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                _VALID_CASES.to_excel(writer, sheet_name="Cases", index=False, header=False)
                bad_rplots.to_excel(writer, sheet_name="Rplots", index=False, header=True)

            issues = check_xls_structure(
                xlsx, ScenarioLoadOptions(tplots_sheet=None, output_sheet=None)
            )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].sheet, "Rplots")
        self.assertIn("property", issues[0].message)

    def test_output_sheet_too_few_columns(self) -> None:
        bad_output = pd.DataFrame([["PIPE P1", "Head"]])
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(
                td,
                {"Cases": _VALID_CASES, "Output": bad_output},
                header=False,
            )

            issues = check_xls_structure(
                xlsx, ScenarioLoadOptions(rplots_sheet=None, tplots_sheet=None)
            )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].sheet, "Output")
        self.assertIn("at least 3 columns", issues[0].message)

    def test_multiple_problems_are_all_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            issues = check_xls_structure(xlsx, ScenarioLoadOptions())

        sheets = {issue.sheet for issue in issues}
        # Cases sheet missing, plus Rplots/Tplots/Output sheets missing.
        self.assertEqual(sheets, {"Cases", "Rplots", "Tplots", "Output"})


class TestMapperDispatch(unittest.TestCase):
    def test_check_scenario_file_delegates_to_xls_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            issues = check_scenario_file(xlsx)

        self.assertTrue(issues)
        self.assertTrue(any(issue.sheet == "Cases" for issue in issues))

    def test_check_scenario_file_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            check_scenario_file("does-not-exist.xlsx")

    def test_assert_scenario_file_valid_raises_with_all_issues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            xlsx = _write_workbook(td, {"Other": pd.DataFrame({"a": [1]})})

            with self.assertRaises(ValueError) as ctx:
                assert_scenario_file_valid(xlsx)

        message = str(ctx.exception)
        self.assertIn("Cases", message)
        self.assertIn("Rplots", message)

    def test_assert_scenario_file_valid_passes_for_example_fixture(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2] / "data" / "scenarios" / "ExampleParameter.xls"
        )
        assert_scenario_file_valid(fixture)


if __name__ == "__main__":
    unittest.main()

