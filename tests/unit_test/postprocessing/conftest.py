"""Shared pytest fixtures for postprocessing tests."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must be set before any test file imports matplotlib.pyplot

import pytest

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


@pytest.fixture
def parquet_cache(tmp_path) -> ParquetCache:
    return ParquetCache(tmp_path)


@pytest.fixture
def make_case_ctx(tmp_path):
    def _factory(meta_overrides=None) -> CaseContext:
        meta_dict = {"Number": 1, "Include": True, "Name": "case_001"}
        meta_dict.update(meta_overrides or {})
        return CaseContext(
            cache=ParquetCache(tmp_path),
            scenario=ScenarioSpecification(meta=ScenarioMeta.model_validate(meta_dict)),
            case_dir=tmp_path,
        )

    return _factory
