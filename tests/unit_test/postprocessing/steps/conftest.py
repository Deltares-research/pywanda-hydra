"""Shared pytest fixtures for postprocessing step tests."""

from __future__ import annotations

import pytest

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import (
    AnalysisMeta,
    PostProcessingConfiguration,
    ReportConfiguration,
    ScenarioSpecification,
)


@pytest.fixture
def make_report_ctx(tmp_path):
    def _factory(
        meta_overrides: dict | None = None,
        analysis_overrides: dict | None = None,
    ) -> CaseContext:
        meta_dict = {"Number": 7, "Include": True, "Name": "case_007"}
        meta_dict.update(meta_overrides or {})
        report_keys = {"Description", "Appendix", "Chapter", "Date"}
        report = ReportConfiguration(
            description=meta_dict.get("Description"),
            appendix=meta_dict.get("Appendix"),
            chapter=meta_dict.get("Chapter"),
            date=meta_dict.get("Date"),
        )
        extra_columns = {
            k: v
            for k, v in meta_dict.items()
            if k not in {"Number", "Include", "Name"} and k not in report_keys
        }
        scenario = ScenarioSpecification(
            number=meta_dict["Number"],
            include=meta_dict["Include"],
            name=meta_dict["Name"],
            post_processing=PostProcessingConfiguration(report=report),
            extra_columns=extra_columns,
        )
        return CaseContext(
            cache=ParquetCache(tmp_path),
            scenario=scenario,
            analysis_metadata=AnalysisMeta.model_validate(analysis_overrides or {}),
            case_dir=tmp_path,
        )

    return _factory
