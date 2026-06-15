"""Unit tests for postprocessing.steps.report_meta."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.steps.report_meta import _format_date, build_report_meta
from pywandahydra.scenarios.schema import AnalysisMeta, ScenarioMeta, ScenarioSpecification


def _make_ctx(tmp_path: Path, meta_overrides: dict, analysis_overrides: dict | None = None) -> CaseContext:
    meta_dict = {"Number": 7, "Include": True, "Name": "case_007"}
    meta_dict.update(meta_overrides)
    scenario = ScenarioSpecification(
        meta=ScenarioMeta.model_validate(meta_dict),
        analysis_meta=AnalysisMeta.model_validate(analysis_overrides or {}),
    )
    return CaseContext(cache=ParquetCache(tmp_path), scenario=scenario, case_dir=tmp_path)


class TestFormatDate(unittest.TestCase):
    def test_none_returns_today(self) -> None:
        result = _format_date(None)

        self.assertEqual(result, date.today().strftime("%d-%m-%Y"))

    def test_datetime_formatted(self) -> None:
        result = _format_date(datetime(2024, 3, 5, 12, 30))

        self.assertEqual(result, "05-03-2024")

    def test_date_formatted(self) -> None:
        result = _format_date(date(2024, 3, 5))

        self.assertEqual(result, "05-03-2024")

    def test_empty_string_returns_today(self) -> None:
        result = _format_date("   ")

        self.assertEqual(result, date.today().strftime("%d-%m-%Y"))

    def test_iso_string_parsed(self) -> None:
        result = _format_date("2024-03-05")

        self.assertEqual(result, "05-03-2024")

    def test_slash_string_parsed(self) -> None:
        result = _format_date("05/03/2024")

        self.assertEqual(result, "05-03-2024")

    def test_unparseable_string_returned_as_is(self) -> None:
        result = _format_date("not-a-date")

        self.assertEqual(result, "not-a-date")


class TestBuildReportMeta(unittest.TestCase):
    def test_with_appendix_builds_figure_id_from_appendix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(
                Path(tmp_dir),
                {
                    "Appendix": "A",
                    "Number": 3,
                    "Chapter": 2,
                    "Description": "Scenario desc",
                    "Date": "2024-01-15",
                },
                {
                    "analysis_description": "Analysis desc",
                    "wanda_version": "WANDA 4.6",
                    "project_number": 123,
                },
            )

            meta = build_report_meta(ctx)

            self.assertEqual(meta.figure_id, "A.003")
            self.assertEqual(meta.chapter, "Chapter 2")
            self.assertEqual(meta.analysis_description, "Analysis desc")
            self.assertEqual(meta.scenario_description, "Scenario desc")
            self.assertEqual(meta.project_number, "123")
            self.assertEqual(meta.wanda_version, "WANDA 4.6")
            self.assertEqual(meta.report_date, "15-01-2024")
            self.assertEqual(meta.case_name, "case_007")

    def test_without_appendix_uses_case_dir_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            case_dir = Path(tmp_dir) / "case_007"
            case_dir.mkdir()
            ctx = _make_ctx(case_dir, {})

            meta = build_report_meta(ctx)

            self.assertEqual(meta.figure_id, "case_007_")

    def test_without_chapter_is_empty_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), {})

            meta = build_report_meta(ctx)

            self.assertEqual(meta.chapter, "")

    def test_scenario_description_falls_back_to_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), {"Extra": "extra text"})

            meta = build_report_meta(ctx)

            self.assertEqual(meta.scenario_description, "extra text")

    def test_missing_analysis_fields_default_to_empty_or_wanda(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), {})

            meta = build_report_meta(ctx)

            self.assertEqual(meta.analysis_description, "")
            self.assertEqual(meta.project_number, "")
            self.assertEqual(meta.wanda_version, "WANDA")


if __name__ == "__main__":
    unittest.main()
