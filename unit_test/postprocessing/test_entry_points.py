from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from pywandahydra.postprocessing.core.context import (
    CaseContext,
    PostProcessingRunContext,
)
from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme
from pywandahydra.postprocessing.plotting.theme_registry import (
    bootstrap as bootstrap_themes,
)
from pywandahydra.postprocessing.plotting.theme_registry import list_themes
from pywandahydra.postprocessing.workflows import bootstrap as bootstrap_workflows
from pywandahydra.postprocessing.workflows import (
    list_case_steps,
    list_run_steps,
    list_workflows,
)
from pywandahydra.postprocessing.workflows.base import resolve_workflow
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

    def run(self, ctx: PostProcessingRunContext) -> None:
        del ctx


class _DummyWorkflow:
    name = "dummy_workflow"
    description = "dummy"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: BaseModel) -> None:
        self._p = params

    def case_steps(self, ctx: CaseContext):
        del ctx
        return [_DummyCaseStep()]

    def run_steps(self, ctx: PostProcessingRunContext):
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
    def test_workflow_bootstrap_loads_entry_points(self) -> None:
        def _eps(*, group: str):
            if group == "pywandahydra.workflows":
                return [_FakeEntryPoint("dummy_workflow", _DummyWorkflow)]
            if group == "pywandahydra.case_steps":
                return [_FakeEntryPoint("dummy_case_step", _DummyCaseStep)]
            if group == "pywandahydra.run_steps":
                return [_FakeEntryPoint("dummy_run_step", _DummyRunStep)]
            return []

        with patch("pywandahydra.postprocessing.workflows.entry_points", _eps):
            bootstrap_workflows()

        self.assertIn("dummy_workflow", list_workflows())
        self.assertIn("dummy_case_step", list_case_steps())
        self.assertIn("dummy_run_step", list_run_steps())

        workflow = resolve_workflow("dummy_workflow")
        self.assertEqual(workflow.name, "dummy_workflow")

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

        with patch(
            "pywandahydra.postprocessing.plotting.theme_registry.entry_points", _eps
        ):
            bootstrap_themes()

        self.assertIn("dummy_theme", list_themes())
