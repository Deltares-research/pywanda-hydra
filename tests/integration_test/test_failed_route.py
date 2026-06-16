"""Evaluate failed route scenarios.

Create runner that evaluates ./tests/data/network.wdi with the following routes:
- Route A: valid
- InvalidRoute: invalid route with large gap between waypoints
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution import runner
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import (
    PostProcessingConfig,
    RoutePlotSpecification,
    ScenarioMeta,
    ScenarioSpecification,
)
from pywandahydra.wanda.locate import find_wanda_bin

DATA_DIR = Path(__file__).parent / "data"


class TestFailedRoute(unittest.TestCase):
    def test_valid_route_extracted_and_invalid_route_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = RunContext(
                run_id="test_failed_route",
                timestamp="20260616T000000Z",
                root_dir=Path(tmp_dir) / "test_failed_route",
            )
            model_spec = ModelSpecification(
                model_path=DATA_DIR / "network.wdi",
                wanda_bin=find_wanda_bin(),
                base_model_name="network",
                readonly=False,
                run_steady=True,
                run_unsteady=False,
            )
            scenario = ScenarioSpecification(
                meta=ScenarioMeta.model_validate(
                    {"Number": 1, "Include": True, "Name": "scenario_001"}
                ),
                post_processing=PostProcessingConfig(
                    routes=[
                        RoutePlotSpecification(route_id="RouteA", property="Pressure"),
                        RoutePlotSpecification(route_id="InvalidRoute", property="Pressure"),
                    ]
                ),
            )

            with patch(
                "pywandahydra.execution.worker.run_postprocessing",
                return_value={"route_plots": True},
            ):
                result = runner.run(
                    model=model_spec,
                    ctx=ctx,
                    scenarios=[scenario],
                    persist_manifest=False,
                )

            self.assertEqual(result.n_success, 1)
            self.assertEqual(result.n_failed, 0)

            case_dir = ctx.root_dir / "scenarios" / "scenario_001"
            cache = ParquetCache(case_dir)
            cached_routes = cache.list_routes()

            self.assertIn("RouteA_Pressure", cached_routes)
            self.assertNotIn("InvalidRoute_Pressure", cached_routes)


if __name__ == "__main__":
    unittest.main()
