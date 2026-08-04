"""Evaluate failed route scenarios.

Create runner that evaluates ./tests/integration_test/data/network.wdi with the following routes:
- Route A: valid
- InvalidRoute: invalid route with large gap between waypoints
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from pywandahydra.execution import runner
from pywandahydra.execution.legacy import ModelSpecification, RunContext
from pywandahydra.results import ParquetResultStore
from pywandahydra.scenarios import (
    FigurePostProcessingConfiguration,
    PostProcessingConfiguration,
    RoutePlotSpecification,
    ScenarioSpecification,
)


class TestFailedRoute(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _inject_fixtures(
        self,
        network_model_spec: ModelSpecification,
        tmp_path: Path,
    ) -> None:
        self.model_spec = network_model_spec
        self.tmp_path = tmp_path

    def test_valid_route_extracted_and_invalid_route_skipped(self) -> None:
        ctx = RunContext(
            run_id="test_failed_route",
            timestamp="20260616T000000Z",
            root_dir=self.tmp_path / "test_failed_route",
        )
        scenario = ScenarioSpecification(
            number=1,
            include=True,
            name="scenario_001",
            post_processing=PostProcessingConfiguration(
                figures=FigurePostProcessingConfiguration(
                    routes=[
                        RoutePlotSpecification(route_id="RouteA", property="Pressure"),
                        RoutePlotSpecification(route_id="InvalidRoute", property="Pressure"),
                    ]
                )
            ),
        )

        result = runner.run(
            model=self.model_spec,
            ctx=ctx,
            scenarios=[scenario],
            persist_manifest=False,
        )

        self.assertEqual(result.n_success, 1)
        self.assertEqual(result.n_failed, 0)

        case_dir = ctx.root_dir / "scenarios" / "scenario_001"
        data = ParquetResultStore(case_dir / "results").read()
        assert data is not None
        cached_routes = {f"{route.route_id}_{route.property}" for route in data.routes}

        self.assertIn("RouteA_Pressure", cached_routes)
        self.assertNotIn("InvalidRoute_Pressure", cached_routes)

