"""Unit tests for preflight model validation."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pywandahydra.config.models import ModelSpecification
from pywandahydra.scenarios.schema import (
    AnalysisMeta,
    ParameterChange,
    PostProcessingConfig,
    ScenarioMeta,
    ScenarioSpecification,
)
from pywandahydra.wanda.api import WandaItemRef
from pywandahydra.wanda.validation import assert_preflight_valid


class _FakeProp:
    pass


class _FakeItem:
    def __init__(self, properties: set[str]) -> None:
        self._properties = properties

    def get_property(self, name: str) -> _FakeProp:
        if name not in self._properties:
            raise KeyError(name)
        return _FakeProp()


class _FakeModel:
    def __init__(self) -> None:
        self._item = _FakeItem({"Head"})

    def get_property(self, name: str) -> _FakeProp:
        if name != "Time step":
            raise KeyError(name)
        return _FakeProp()

    def get_component(self, name: str) -> _FakeItem:
        if name != "PIPE P1":
            raise KeyError(name)
        return self._item


@contextmanager
def _fake_wanda_session(spec: ModelSpecification, *, model_path: Path | None = None):
    del spec, model_path
    yield _FakeModel()


class TestPreflightValidation(unittest.TestCase):
    def _model_spec(self) -> ModelSpecification:
        return ModelSpecification(
            model_path=Path("base_model.wdi"),
            wanda_bin=Path("."),
            base_model_name="base_model",
            run_steady=True,
            run_unsteady=False,
            readonly=True,
        )

    def _scenario(
        self, *, component: str, property_name: str, value: object
    ) -> ScenarioSpecification:
        meta = ScenarioMeta.model_validate(
            {
                "Number": 1,
                "Include": True,
                "Name": "case_001",
                "Description": None,
                "Extra": None,
                "Appendix": None,
                "Chapter": None,
                "Date": None,
            }
        )
        return ScenarioSpecification(
            meta=meta,
            analysis_meta=AnalysisMeta(),
            parameters=[
                ParameterChange(
                    component=component, property=property_name, value=value
                )
            ],
            post_processing=PostProcessingConfig(),
            source={},
        )

    def test_preflight_fails_on_missing_component(self) -> None:
        scenarios = [
            self._scenario(component="MISSING", property_name="Head", value=1.0)
        ]

        with (
            patch("pywandahydra.wanda.validation.wanda_session", _fake_wanda_session),
            patch("pywandahydra.wanda.validation.resolve_items", return_value=[]),
            self.assertRaises(ValueError),
        ):
            # isolated=False keeps validation in-process so the patches above
            # apply (they do not cross a spawned subprocess boundary).
            assert_preflight_valid(
                model_spec=self._model_spec(),
                scenarios=scenarios,
                isolated=False,
            )

    def test_preflight_accepts_legacy_disuse_zero(self) -> None:
        scenarios = [
            self._scenario(component="PIPE P1", property_name="disuse", value=0)
        ]

        with (
            patch("pywandahydra.wanda.validation.wanda_session", _fake_wanda_session),
            patch(
                "pywandahydra.wanda.validation.resolve_items",
                return_value=[WandaItemRef("PIPE P1", "component")],
            ),
        ):
            assert_preflight_valid(
                model_spec=self._model_spec(),
                scenarios=scenarios,
                isolated=False,
            )
