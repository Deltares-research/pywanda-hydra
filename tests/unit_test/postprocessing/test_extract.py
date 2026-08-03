"""Unit tests for postprocessing.extraction.extract."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from pywandahydra.postprocessing.extraction.extract import (
    extract_all,
    extract_component_outputs,
    extract_route_outputs,
)
from pywandahydra.scenarios import (
    FigurePostProcessingConfiguration,
    MinMaxTableSpecification,
    PostProcessingConfiguration,
    ScenarioSpecification,
    TablePostProcessingConfiguration,
    TimeSeriesPlotSpecification,
)
from pywandahydra.scenarios.models.plot_route import RoutePlotSpecification


class _FakeAdapter:
    """In-memory adapter returning canned data for extraction tests."""

    def __init__(
        self,
        *,
        time_steps: list[float],
        resolve_map: dict[str, list[str]] | None = None,
        pipe_items: set[str] | None = None,
        series: dict[tuple[str, str], np.ndarray] | None = None,
        pipe_series: dict[tuple[str, str], np.ndarray] | None = None,
        pipe_lengths: dict[str, float] | None = None,
        pipe_extrema: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] | None = None,
        pipe_profiles: dict[str, np.ndarray] | None = None,
        route_pipes: dict[str, list[tuple[str, int]]] | None = None,
        is_pipe_raises: set[str] | None = None,
    ) -> None:
        self._time_steps = time_steps
        self._resolve_map = resolve_map or {}
        self._pipe_items = pipe_items or set()
        self._series = series or {}
        self._pipe_series = pipe_series or {}
        self._pipe_lengths = pipe_lengths or {}
        self._pipe_extrema = pipe_extrema or {}
        self._pipe_profiles = pipe_profiles or {}
        self._route_pipes = route_pipes or {}
        self._is_pipe_raises = is_pipe_raises or set()

    def get_time_steps(self, handle):
        del handle
        return list(self._time_steps)

    def resolve_output_items(self, handle, identifier):
        del handle
        return list(self._resolve_map.get(identifier, []))

    def is_pipe_item(self, handle, item_name):
        del handle
        if item_name in self._is_pipe_raises:
            raise RuntimeError(f"no such item: {item_name}")
        return item_name in self._pipe_items

    def get_series(self, handle, component, property_name):
        del handle
        return self._series[(component, property_name)]

    def get_pipe_series(self, handle, pipe_name, property_name):
        del handle
        return self._pipe_series[(pipe_name, property_name)]

    def get_pipe_length(self, handle, pipe_name):
        del handle
        return self._pipe_lengths[pipe_name]

    def get_pipe_extrema(self, handle, pipe_name, property_name):
        del handle
        return self._pipe_extrema[(pipe_name, property_name)]

    def get_pipe_profile_table(self, handle, pipe_name):
        del handle
        return self._pipe_profiles[pipe_name]

    def resolve_route_pipes(self, handle, route_id):
        del handle
        return list(self._route_pipes.get(route_id, []))


class TestExtractComponentOutputs(unittest.TestCase):
    def test_empty_specs_returns_empty_dataframe(self) -> None:
        adapter = _FakeAdapter(time_steps=[0.0, 1.0])

        result = extract_component_outputs(None, [], adapter)  # type: ignore[arg-type]

        self.assertTrue(result.empty)

    def test_missing_component_skipped(self) -> None:
        adapter = _FakeAdapter(time_steps=[0.0, 1.0], resolve_map={})
        specs = [MinMaxTableSpecification(component="MISSING", property="Head", mode="MAX")]

        result = extract_component_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertTrue(result.empty)

    def test_non_pipe_component_produces_single_column(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0, 2.0],
            resolve_map={"PUMP P1": ["PUMP P1"]},
            pipe_items=set(),
            series={("PUMP P1", "Head"): np.array([1.0, 2.0, 3.0])},
        )
        specs = [MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")]

        result = extract_component_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(result.shape, (3, 1))
        col = result.columns[0]
        self.assertEqual(col[:2], ("PUMP P1", "Head"))
        self.assertTrue(np.isnan(col[2]))
        self.assertEqual(result.iloc[:, 0].tolist(), [1.0, 2.0, 3.0])

    def test_pipe_component_produces_multiple_s_location_columns(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            resolve_map={"PIPE P1": ["PIPE P1"]},
            pipe_items={"PIPE P1"},
            pipe_series={("PIPE P1", "Pressure"): np.array([[1.0, 2.0], [3.0, 4.0]])},
            pipe_lengths={"PIPE P1": 10.0},
        )
        specs = [MinMaxTableSpecification(component="PIPE P1", property="Pressure", mode="MAX")]

        result = extract_component_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(result.shape, (2, 2))
        s_locations = sorted(col[2] for col in result.columns)
        self.assertEqual(s_locations, [0.0, 10.0])

    def test_is_pipe_item_error_skips_spec(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            resolve_map={"PUMP P1": ["PUMP P1"]},
            is_pipe_raises={"PUMP P1"},
        )
        specs = [MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")]

        result = extract_component_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertTrue(result.empty)

    def test_duplicate_component_property_deduplicated(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            resolve_map={"PUMP P1": ["PUMP P1"]},
            series={("PUMP P1", "Head"): np.array([1.0, 2.0])},
        )
        specs = [
            MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX"),
            TimeSeriesPlotSpecification(component="PUMP P1", property="Head"),
        ]

        result = extract_component_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(result.shape, (2, 1))


class TestExtractRouteOutputs(unittest.TestCase):
    def test_empty_specs_returns_empty_dict(self) -> None:
        adapter = _FakeAdapter(time_steps=[0.0, 1.0])

        result = extract_route_outputs(None, [], adapter)  # type: ignore[arg-type]

        self.assertEqual(result, {})

    def test_blank_route_id_skipped(self) -> None:
        adapter = _FakeAdapter(time_steps=[0.0, 1.0])
        specs = [RoutePlotSpecification(route_id="   ", property="Pressure", title="t")]

        result = extract_route_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(result, {})

    def test_route_with_no_pipes_skipped(self) -> None:
        adapter = _FakeAdapter(time_steps=[0.0, 1.0], route_pipes={})
        specs = [RoutePlotSpecification(route_id="Route A", property="Pressure", title="t")]

        result = extract_route_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(result, {})

    def test_single_forward_pipe_route(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            route_pipes={"Route A": [("PIPE P1", 1)]},
            pipe_series={("PIPE P1", "Pressure"): np.array([[1.0, 2.0], [3.0, 4.0]])},
            pipe_lengths={"PIPE P1": 10.0},
            pipe_extrema={("PIPE P1", "Pressure"): (np.array([0.0, 1.0]), np.array([5.0, 6.0]))},
            pipe_profiles={
                "PIPE P1": np.array(
                    [
                        [0.0, 0.0],
                        [100.0, 110.0],
                        [0.0, 10.0],
                    ]
                )
            },
        )
        specs = [RoutePlotSpecification(route_id="Route A", property="Pressure", title="Route A")]

        result = extract_route_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertIn("Route A", result)
        route_result = result["Route A"]
        self.assertEqual(set(route_result.keys()), {"timeseries", "envelope", "profile"})

        ts = route_result["timeseries"]
        self.assertEqual(ts.shape, (2, 2))
        s_locations = sorted(col[2] for col in ts.columns)
        self.assertEqual(s_locations, [0.0, 10.0])

        env = route_result["envelope"]
        self.assertEqual(list(env.index), [0.0, 10.0])
        self.assertEqual(env["min"].tolist(), [0.0, 1.0])
        self.assertEqual(env["max"].tolist(), [5.0, 6.0])

        profile = route_result["profile"]
        self.assertEqual(list(profile.index), [0.0, 10.0])
        self.assertEqual(profile["elevation"].tolist(), [100.0, 110.0])

    def test_reverse_direction_pipe_reverses_s_location(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            route_pipes={"Route B": [("PIPE P1", -1)]},
            pipe_series={("PIPE P1", "Pressure"): np.array([[1.0, 2.0], [3.0, 4.0]])},
            pipe_lengths={"PIPE P1": 10.0},
            pipe_extrema={("PIPE P1", "Pressure"): (np.array([0.0, 1.0]), np.array([5.0, 6.0]))},
            pipe_profiles={
                "PIPE P1": np.array(
                    [
                        [0.0, 0.0],
                        [100.0, 110.0],
                        [0.0, 10.0],
                    ]
                )
            },
        )
        specs = [RoutePlotSpecification(route_id="Route B", property="Pressure", title="Route B")]

        result = extract_route_outputs(None, specs, adapter)  # type: ignore[arg-type]

        ts = result["Route B"]["timeseries"]
        s_locations = sorted(col[2] for col in ts.columns)
        self.assertEqual(s_locations, [0.0, 10.0])

        env = result["Route B"]["envelope"]
        # reversed: s_env = length - s_local_env => [10, 0]; sorted index ascending
        self.assertEqual(sorted(env.index), [0.0, 10.0])

        profile = result["Route B"]["profile"]
        self.assertEqual(sorted(profile.index), [0.0, 10.0])

    def test_duplicate_titles_get_suffixed(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            route_pipes={"Route A": [("PIPE P1", 1)], "Route B": [("PIPE P1", 1)]},
            pipe_series={("PIPE P1", "Pressure"): np.array([[1.0, 2.0], [3.0, 4.0]])},
            pipe_lengths={"PIPE P1": 10.0},
            pipe_extrema={("PIPE P1", "Pressure"): (np.array([0.0, 1.0]), np.array([5.0, 6.0]))},
            pipe_profiles={"PIPE P1": np.array([[0.0, 0.0], [100.0, 110.0], [0.0, 10.0]])},
        )
        specs = [
            RoutePlotSpecification(route_id="Route A", property="Pressure", title="Same"),
            RoutePlotSpecification(route_id="Route B", property="Pressure", title="Same"),
        ]

        result = extract_route_outputs(None, specs, adapter)  # type: ignore[arg-type]

        self.assertEqual(set(result.keys()), {"Same", "Same_2"})


class TestExtractAll(unittest.TestCase):
    def test_combines_tables_time_plots_and_routes(self) -> None:
        adapter = _FakeAdapter(
            time_steps=[0.0, 1.0],
            resolve_map={"PUMP P1": ["PUMP P1"]},
            series={("PUMP P1", "Head"): np.array([1.0, 2.0])},
            route_pipes={"Route A": [("PIPE P1", 1)]},
            pipe_series={("PIPE P1", "Pressure"): np.array([[1.0, 2.0], [3.0, 4.0]])},
            pipe_lengths={"PIPE P1": 10.0},
            pipe_extrema={("PIPE P1", "Pressure"): (np.array([0.0, 1.0]), np.array([5.0, 6.0]))},
            pipe_profiles={"PIPE P1": np.array([[0.0, 0.0], [100.0, 110.0], [0.0, 10.0]])},
        )
        scenario = ScenarioSpecification(
            number=1,
            include=True,
            name="case_001",
            post_processing=PostProcessingConfiguration(
                tables=TablePostProcessingConfiguration(
                    minmax=[
                        MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")
                    ]
                ),
                figures=FigurePostProcessingConfiguration(
                    routes=[
                        RoutePlotSpecification(
                            route_id="Route A", property="Pressure", title="Route A"
                        )
                    ]
                ),
            ),
        )

        result = extract_all(None, scenario, adapter)  # type: ignore[arg-type]

        self.assertIn("components", result)
        self.assertIn("routes", result)
        self.assertIsInstance(result["components"], pd.DataFrame)
        self.assertFalse(result["components"].empty)
        self.assertIn("Route A", result["routes"])


if __name__ == "__main__":
    unittest.main()

