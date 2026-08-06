"""Shared pytest fixtures for postprocessing tests."""

from __future__ import annotations

from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")  # must be set before any test file imports matplotlib.pyplot

import pytest

from pywandahydra.results import ParquetResultStore
from pywandahydra.scenarios import (
    PostProcessingConfiguration,
    ReportConfiguration,
    ScenarioSpecification,
)


@pytest.fixture
def result_store(tmp_path) -> ParquetResultStore:
    return ParquetResultStore(tmp_path / "results")


@pytest.fixture
def make_case_ctx(tmp_path):
    def _factory(meta_overrides=None) -> SimpleNamespace:
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
        return SimpleNamespace(
            store=ParquetResultStore(tmp_path / "results"),
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

