"""Unit tests for wanda.pywanda_adapter (real pywanda, no simulation run)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import numpy as np

from pywandahydra.config.models import ModelSpecification
from pywandahydra.scenarios.schema import ParameterChange
from pywandahydra.wanda.create_scenario import prepare_scenario_model
from pywandahydra.wanda.locate import find_wanda_bin
from pywandahydra.wanda.pywanda_adapter import PywandaAdapter


class TestPywandaAdapter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            wanda_bin = find_wanda_bin()
        except FileNotFoundError as exc:
            self.skipTest(f"WANDA not available: {exc}")

        base_dir = Path(__file__).parents[2] / "test_data" / "wanda"
        self.model_spec = ModelSpecification(
            model_path=base_dir / "base_model.wdi",
            wanda_bin=wanda_bin,
            base_model_name="base_model",
            run_steady=False,
            run_unsteady=False,
            readonly=False,
        )

        self.scenario_dir = base_dir / "test_scenario_adapter"
        self.adapter = PywandaAdapter()
        self.scenario_model_path = self.adapter.prepare_scenario_model(
            self.model_spec.model_path,
            self.scenario_dir,
            "test_scenario_adapter",
            readonly=False,
        )

    def tearDown(self) -> None:
        for ext in (".wdi", ".wdx"):
            path = self.scenario_dir / f"base_model_test_scenario_adapter{ext}"
            if path.exists():
                path.unlink()
        try:
            self.scenario_dir.rmdir()
        except OSError:
            pass

    def get_session(self):
        return self.adapter.session(self.model_spec, self.scenario_model_path)

    def test_open_and_close_via_session(self) -> None:
        with self.get_session() as model:
            self.assertIsNotNone(model)
            self.assertEqual(len(model.get_all_pipes()), 3)

        with self.assertRaises(Exception):
            model.get_model_name()

    def test_apply_general_change_and_save_input(self) -> None:
        with self.get_session() as model:
            change = ParameterChange(component="general", property="Time step", value=12.5)

            self.adapter.apply(model, change)
            self.adapter.save_input(model)

            self.assertEqual(model.get_property("Time step").get_scalar_float(), 12.5)

    def test_simulation_time_and_get_simulation_time(self) -> None:
        with self.get_session() as model:
            self.assertEqual(self.adapter.simulation_time(model), 20.0)
            self.assertEqual(self.adapter.get_simulation_time(model), 20.0)

    def test_resolve_route_components_for_all_pipes(self) -> None:
        with self.get_session() as model:
            names = self.adapter.resolve_route_components(model, "PALL")

            self.assertEqual(set(names), {"PIPE P1", "PIPE P2", "PIPE 74go82"})

    def test_resolve_output_items_for_exact_component(self) -> None:
        with self.get_session() as model:
            names = self.adapter.resolve_output_items(model, "PIPE P1")

            self.assertEqual(names, ["PIPE P1"])

    def test_resolve_output_items_for_missing_component(self) -> None:
        with self.get_session() as model:
            names = self.adapter.resolve_output_items(model, "DOES NOT EXIST")

            self.assertEqual(names, [])

    def test_is_pipe_item_true_for_pipe(self) -> None:
        with self.get_session() as model:
            self.assertTrue(self.adapter.is_pipe_item(model, "PIPE P1"))

    def test_is_pipe_item_false_for_non_pipe(self) -> None:
        with self.get_session() as model:
            self.assertFalse(self.adapter.is_pipe_item(model, "PUMP P1"))

    def test_get_pipe_length(self) -> None:
        with self.get_session() as model:
            length = self.adapter.get_pipe_length(model, "PIPE P1")

            self.assertGreater(length, 0.0)

    def test_get_pipe_length_raises_for_non_pipe(self) -> None:
        with self.get_session() as model:
            with self.assertRaises(ValueError):
                self.adapter.get_pipe_length(model, "PUMP P1")

    def test_get_pipe_profile_table(self) -> None:
        with self.get_session() as model:
            table = self.adapter.get_pipe_profile_table(model, "PIPE P1")

            self.assertIsInstance(table, np.ndarray)
            self.assertEqual(table.ndim, 2)

    def test_get_scalar_for_length_property(self) -> None:
        with self.get_session() as model:
            length = self.adapter.get_scalar(model, "PIPE P1", "Length")

            self.assertGreater(length, 0.0)

    def test_get_scalar_for_missing_component_raises(self) -> None:
        with self.get_session() as model:
            with self.assertRaises(ValueError):
                self.adapter.get_scalar(model, "DOES NOT EXIST", "Length")

    def test_resolve_route_pipes_for_single_pipe(self) -> None:
        with self.get_session() as model:
            pipes = self.adapter.resolve_route_pipes(model, "PIPE P1")

            self.assertEqual(pipes, [("PIPE P1", 1)])

    def test_get_item_by_name_raises_for_missing_item(self) -> None:
        with self.get_session() as model:
            with self.assertRaises(ValueError):
                self.adapter._get_item_by_name(model, "DOES NOT EXIST")

    def test_get_item_by_name_falls_back_to_first_match(self) -> None:
        with self.get_session() as model:
            # "PG1" is a keyword matching multiple pumps; no exact name match
            # exists, so the adapter falls back to the first resolved item.
            item = self.adapter._get_item_by_name(model, "PG1")

            self.assertEqual(item.get_complete_name_spec(), "PUMP P1")

    def test_open_close_save_and_apply_delegation(self) -> None:
        with self.get_session() as model:
            self.adapter.run_steady(model)

            # open()/close() delegate to pywanda.WandaModel directly.
            opened_model = self.adapter.open(
                str(self.scenario_model_path), str(self.model_spec.wanda_bin) + os.sep
            )
            self.adapter.close(opened_model)

            # save_model_input() delegates to handle.save_model_input().
            self.adapter.save_model_input(model)

            # apply_parameter_change() delegates to the api module function.
            change = ParameterChange(component="general", property="Time step", value=10.0)
            self.adapter.apply_parameter_change(model, change)

            self.assertEqual(model.get_property("Time step").get_scalar_float(), 10.0)

    def test_run_steady_and_get_time_steps(self) -> None:
        with self.get_session() as model:
            self.adapter.run_steady(model)

            time_steps = self.adapter.get_time_steps(model)

            self.assertIsInstance(time_steps, list)
            self.assertGreaterEqual(len(time_steps), 1)


if __name__ == "__main__":
    unittest.main()
