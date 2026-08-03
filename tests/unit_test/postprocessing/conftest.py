"""Shared pytest fixtures for postprocessing tests."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must be set before any test file imports matplotlib.pyplot

import pytest

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios import (
    PostProcessingConfiguration,
    ReportConfiguration,
    ScenarioSpecification,
)


@pytest.fixture
def parquet_cache(tmp_path) -> ParquetCache:
    return ParquetCache(tmp_path)


@pytest.fixture
def make_case_ctx(tmp_path):
    def _factory(meta_overrides=None) -> CaseContext:
        meta_dict = {"Number": 1, "Include": True, "Name": "case_001"}
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
        return CaseContext(
            cache=ParquetCache(tmp_path),
            scenario=ScenarioSpecification(
                number=meta_dict["Number"],
                include=meta_dict["Include"],
                name=meta_dict["Name"],
                post_processing=PostProcessingConfiguration(report=report),
                extra_columns=extra_columns,
            ),
            case_dir=tmp_path,
        )

    return _factory

