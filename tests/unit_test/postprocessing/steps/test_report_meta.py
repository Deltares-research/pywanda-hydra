"""Unit tests for postprocessing.steps.report_meta."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

from pywandahydra.postprocessing.steps.report_meta import _format_date, build_report_meta


def test_format_date_none_returns_today() -> None:
    result = _format_date(None)

    assert result == date.today().strftime("%d-%m-%Y")


def test_format_date_datetime_formatted() -> None:
    result = _format_date(datetime(2026, 3, 5, 12, 30))

    assert result == "05-03-2026"


def test_format_date_date_formatted() -> None:
    result = _format_date(date(2026, 3, 5))

    assert result == "05-03-2026"


def test_format_date_empty_string_returns_today() -> None:
    result = _format_date("   ")

    assert result == date.today().strftime("%d-%m-%Y")


def test_format_date_iso_string_parsed() -> None:
    result = _format_date("2026-03-05")

    assert result == "05-03-2026"


def test_format_date_slash_string_parsed() -> None:
    result = _format_date("05/03/2026")

    assert result == "05-03-2026"


def test_format_date_unparseable_string_returned_as_is() -> None:
    result = _format_date("not-a-date")

    assert result == "not-a-date"


def test_with_appendix_builds_figure_id_from_appendix(make_report_ctx) -> None:
    ctx = make_report_ctx(
        {
            "Appendix": "A",
            "Number": 3,
            "Chapter": 2,
            "Description": "Scenario desc",
            "Date": "2026-01-15",
        },
        {
            "analysis_description": "Analysis desc",
            "wanda_version": "WANDA 4.6",
            "project_number": 123,
        },
    )

    meta = build_report_meta(ctx)

    assert meta.figure_id == "A.003"
    assert meta.chapter == "Chapter 2"
    assert meta.analysis_description == "Analysis desc"
    assert meta.scenario_description == "Scenario desc"
    assert meta.project_number == "123"
    assert meta.wanda_version == "WANDA 4.6"
    assert meta.report_date == "15-01-2026"
    assert meta.case_name == "case_007"


def test_without_appendix_uses_case_dir_name(make_report_ctx, tmp_path) -> None:
    case_dir = tmp_path / "case_007"
    case_dir.mkdir()
    ctx = dataclasses.replace(make_report_ctx(), case_dir=case_dir)

    meta = build_report_meta(ctx)

    assert meta.figure_id == "case_007_"


def test_without_chapter_is_empty_string(make_report_ctx) -> None:
    ctx = make_report_ctx()

    meta = build_report_meta(ctx)

    assert meta.chapter == ""


def test_scenario_description_falls_back_to_extra(make_report_ctx) -> None:
    ctx = make_report_ctx({"Extra": "extra text"})

    meta = build_report_meta(ctx)

    assert meta.scenario_description == "extra text"


def test_missing_analysis_fields_default_to_empty_or_wanda(make_report_ctx) -> None:
    ctx = make_report_ctx()

    meta = build_report_meta(ctx)

    assert meta.analysis_description == ""
    assert meta.project_number == ""
    assert meta.wanda_version == "WANDA"
