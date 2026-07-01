"""Shared pytest fixtures for postprocessing step tests."""

from __future__ import annotations

import pytest

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import AnalysisMeta, ScenarioMeta, ScenarioSpecification


@pytest.fixture
def make_report_ctx(tmp_path):
    def _factory(
        meta_overrides: dict | None = None,
        analysis_overrides: dict | None = None,
    ) -> CaseContext:
        meta_dict = {"Number": 7, "Include": True, "Name": "case_007"}
        meta_dict.update(meta_overrides or {})
        scenario = ScenarioSpecification(
            meta=ScenarioMeta.model_validate(meta_dict),
            analysis_meta=AnalysisMeta.model_validate(analysis_overrides or {}),
        )
        return CaseContext(cache=ParquetCache(tmp_path), scenario=scenario, case_dir=tmp_path)

    return _factory
