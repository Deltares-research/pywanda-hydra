"""Unit tests for preflight model validation."""

from __future__ import annotations

# Import shared helper from root conftest
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pywandahydra.config.models import ModelSpecification
from pywandahydra.scenarios import (
    FigurePostProcessingConfiguration,
    MinMaxTableSpecification,
    ModelParameterChange,
    PostProcessingConfiguration,
    ScenarioSpecification,
    TablePostProcessingConfiguration,
    TimeSeriesPlotSpecification,
)
from pywandahydra.scenarios.models.plot_route import RoutePlotSpecification
from pywandahydra.wanda.api import WandaItemRef
from pywandahydra.wanda.validation import PreflightValidationError, assert_preflight_valid

sys.path.insert(0, str(Path(__file__).parents[2]))
from conftest import find_wanda_bin


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
            reuse_existing_data=True,
        )

    def _scenario(
        self, *, component: str, property_name: str, value: object
    ) -> ScenarioSpecification:
        return ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            parameter_changes=[
                ModelParameterChange(component=component, property=property_name, value=value)
            ],
            source={},
        )

    def test_preflight_fails_on_missing_component(self) -> None:
        scenarios = [self._scenario(component="MISSING", property_name="Head", value=1.0)]

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

    def test_preflight_accepts_valid_scenario(self) -> None:
        scenarios = [self._scenario(component="PIPE P1", property_name="Head", value=1.0)]

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

    def test_preflight_fails_on_missing_table_property(self) -> None:
        scenario = ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            post_processing=PostProcessingConfiguration(
                tables=TablePostProcessingConfiguration(
                    minmax=[
                        MinMaxTableSpecification(
                            component="PIPE P1", property="Missing", mode="MAX"
                        )
                    ]
                )
            ),
            source={},
        )

        with (
            patch("pywandahydra.wanda.validation.wanda_session", _fake_wanda_session),
            patch(
                "pywandahydra.wanda.validation.resolve_items",
                return_value=[WandaItemRef("PIPE P1", "component")],
            ),
            self.assertRaises(PreflightValidationError) as ctx,
        ):
            assert_preflight_valid(
                model_spec=self._model_spec(),
                scenarios=[scenario],
                isolated=False,
            )

        self.assertIn("post_processing.tables", str(ctx.exception))
        self.assertIn("PIPE P1.Missing", str(ctx.exception))

    def test_preflight_fails_on_missing_route(self) -> None:
        scenario = ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            post_processing=PostProcessingConfiguration(
                figures=FigurePostProcessingConfiguration(
                    routes=[RoutePlotSpecification(route_id="Route A", property="Pressure")]
                )
            ),
            source={},
        )

        with (
            patch("pywandahydra.wanda.validation.wanda_session", _fake_wanda_session),
            patch("pywandahydra.wanda.validation.resolve_items", return_value=[]),
            self.assertRaises(PreflightValidationError) as ctx,
        ):
            assert_preflight_valid(
                model_spec=self._model_spec(),
                scenarios=[scenario],
                isolated=False,
            )

        self.assertIn("post_processing.routes", str(ctx.exception))

    def test_preflight_fails_on_missing_time_plot_property(self) -> None:
        scenario = ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            post_processing=PostProcessingConfiguration(
                figures=FigurePostProcessingConfiguration(
                    time_series=[
                        TimeSeriesPlotSpecification(component="PIPE P1", property="Missing")
                    ]
                )
            ),
            source={},
        )

        with (
            patch("pywandahydra.wanda.validation.wanda_session", _fake_wanda_session),
            patch(
                "pywandahydra.wanda.validation.resolve_items",
                return_value=[WandaItemRef("PIPE P1", "component")],
            ),
            self.assertRaises(PreflightValidationError) as ctx,
        ):
            assert_preflight_valid(
                model_spec=self._model_spec(),
                scenarios=[scenario],
                isolated=False,
            )

        self.assertIn("post_processing.time_plots", str(ctx.exception))
        self.assertIn("PIPE P1.Missing", str(ctx.exception))

    def test_preflight_accepts_legacy_disuse_zero(self) -> None:
        scenarios = [self._scenario(component="PIPE P1", property_name="disuse", value=0)]

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


class TestPreflightValidationIsolated(unittest.TestCase):
    """Exercise the spawned-subprocess preflight path against the real model."""

    def setUp(self) -> None:
        try:
            wanda_bin = find_wanda_bin()
        except FileNotFoundError as exc:
            self.skipTest(f"WANDA not available: {exc}")

        self.model_spec = ModelSpecification(
            model_path=Path(__file__).parents[2] / "data" / "wanda" / "base_model.wdi",
            wanda_bin=wanda_bin,
            base_model_name="base_model",
            run_steady=False,
            run_unsteady=False,
            reuse_existing_data=True,
        )

    def _scenario(
        self, *, component: str, property_name: str, value: object
    ) -> ScenarioSpecification:
        return ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            parameter_changes=[
                ModelParameterChange(component=component, property=property_name, value=value)
            ],
        )

    def test_isolated_validation_accepts_valid_scenario(self) -> None:
        scenario = self._scenario(component="PIPE P1", property_name="Length", value=10.0)

        assert_preflight_valid(model_spec=self.model_spec, scenarios=[scenario], isolated=True)

    def test_isolated_validation_reports_missing_component(self) -> None:
        scenario = self._scenario(component="MISSING COMP", property_name="Length", value=10.0)

        with self.assertRaises(PreflightValidationError) as ctx:
            assert_preflight_valid(model_spec=self.model_spec, scenarios=[scenario], isolated=True)

        self.assertIn("MISSING COMP", str(ctx.exception))

