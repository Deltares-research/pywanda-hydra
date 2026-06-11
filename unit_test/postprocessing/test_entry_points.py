from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from pywandahydra.postprocessing.context import CaseContext, RunStepContext
from pywandahydra.postprocessing.methodologies import (
    bootstrap as bootstrap_methodologies,
)
from pywandahydra.postprocessing.methodologies import (
    list_case_steps,
    list_methodologies,
    list_run_steps,
)
from pywandahydra.postprocessing.methodologies.base import resolve_methodology
from pywandahydra.postprocessing.plotting.renderer import PlotTheme
from pywandahydra.postprocessing.plotting.themes import (
    bootstrap as bootstrap_themes,
)
from pywandahydra.postprocessing.plotting.themes import list_themes
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification
from pywandahydra.scenarios.sources import bootstrap as bootstrap_sources
from pywandahydra.scenarios.sources import list_source_extensions


class _FakeEntryPoint:
    def __init__(self, name: str, obj: Any) -> None:
        self.name = name
        self._obj = obj

    def load(self) -> Any:
        return self._obj


class _DummyCaseStep:
    name = "dummy_case_step"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        del ctx
        return True

    def run(self, ctx: CaseContext) -> None:
        del ctx


class _DummyRunStep:
    name = "dummy_run_step"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: RunStepContext) -> None:
        del ctx


class _DummyMethodology:
    name = "dummy_methodology"
    description = "dummy"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: BaseModel) -> None:
        self._p = params

    def case_steps(self, ctx: CaseContext):
        del ctx
        return [_DummyCaseStep()]

    def run_steps(self, ctx: RunStepContext):
        del ctx
        return [_DummyRunStep()]


class _DummyScenarioSource:
    extensions = {".dummy"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def load(self, path: Path):
        del path
        scenario = ScenarioSpecification(
            meta=ScenarioMeta.model_validate(
                {
                    "Number": 1,
                    "Include": True,
                    "Name": "dummy",
                }
            )
        )
        return [scenario]


class TestEntryPointLoading(unittest.TestCase):
    def test_methodology_bootstrap_loads_entry_points(self) -> None:
        def _eps(*, group: str):
            if group == "pywandahydra.methodologies":
                return [_FakeEntryPoint("dummy_methodology", _DummyMethodology)]
            if group == "pywandahydra.case_steps":
                return [_FakeEntryPoint("dummy_case_step", _DummyCaseStep)]
            if group == "pywandahydra.run_steps":
                return [_FakeEntryPoint("dummy_run_step", _DummyRunStep)]
            return []

        with patch("pywandahydra.postprocessing.methodologies.entry_points", _eps):
            bootstrap_methodologies()

        self.assertIn("dummy_methodology", list_methodologies())
        self.assertIn("dummy_case_step", list_case_steps())
        self.assertIn("dummy_run_step", list_run_steps())

        meth = resolve_methodology("dummy_methodology")
        self.assertEqual(meth.name, "dummy_methodology")

    def test_scenario_source_bootstrap_loads_entry_points(self) -> None:
        def _eps(*, group: str):
            if group == "pywandahydra.scenario_sources":
                return [_FakeEntryPoint("dummy_source", _DummyScenarioSource)]
            return []

        with patch("pywandahydra.scenarios.sources.entry_points", _eps):
            bootstrap_sources()

        self.assertIn(".dummy", list_source_extensions())

    def test_theme_bootstrap_loads_entry_points(self) -> None:
        custom_theme = PlotTheme(axis_title_size=42)

        def _eps(*, group: str):
            if group == "pywandahydra.themes":
                return [_FakeEntryPoint("dummy_theme", custom_theme)]
            return []

        with patch("pywandahydra.postprocessing.plotting.themes.entry_points", _eps):
            bootstrap_themes()

        self.assertIn("dummy_theme", list_themes())
