"""Unit tests for wanda.api module."""

import unittest
from pathlib import Path

from pywandahydra.config.models import ModelSpecification
from pywandahydra.scenarios.schema import ParameterChange
from pywandahydra.wanda.api import (
    WandaItemRef,
    apply_parameter_change,
    find_items_with_keyword,
    get_item,
    resolve_items,
)
from pywandahydra.wanda.create_scenario import prepare_scenario_model
from pywandahydra.wanda.locate import find_wanda_bin
from pywandahydra.wanda.session import wanda_session


class TestWandaAPI(unittest.TestCase):
    """Unit tests for wanda.api functions."""

    def setUp(self) -> None:
        """Set up a Wanda model for testing."""
        try:
            wanda_bin = find_wanda_bin()
        except FileNotFoundError as exc:
            self.skipTest(f"WANDA not available: {exc}")
        self.model_spec = ModelSpecification(
            model_path=Path(__file__).parents[2]
            / "test_data"
            / "wanda"
            / "base_model.wdi",
            wanda_bin=wanda_bin,
            base_model_name="base_model",
            run_steady=False,
            run_unsteady=False,
            readonly=False,
        )

        self.scenario_model_path = (
            Path(__file__).parents[2]
            / "test_data"
            / "wanda"
            / "test_scenario"
            / "base_model_test_scenario.wdi"
        )

        prepare_scenario_model(
            base_model_path=self.model_spec.model_path,
            scenario_dir=Path(__file__).parents[2]
            / "test_data"
            / "wanda"
            / "test_scenario",
            scenario_name="test_scenario",
            readonly=self.model_spec.readonly,
        )

    def get_wanda_session(self):
        """Helper method to create a Wanda session for testing."""
        return wanda_session(spec=self.model_spec, model_path=self.scenario_model_path)

    def test_change_general(self):
        """Test applying a general parameter change."""
        # Arrange
        with self.get_wanda_session() as model:
            # Act
            change = ParameterChange(
                component="general", property="Time step", value=15.0
            )
            apply_parameter_change(model, change)
            time_step_prop = model.get_property("Time step")

            # Assert
            self.assertEqual(time_step_prop.get_scalar_float(), 15.0)

    def test_disuse_component(self):
        """Test applying a 'disuse' parameter change to a component."""
        # Arrange
        with self.get_wanda_session() as model:
            # Act
            change = ParameterChange(component="PUMP P1", property="disuse", value=0)
            apply_parameter_change(model, change)
            pump = model.get_component("PUMP P1")

            # Assert
            self.assertTrue(pump.is_disused())

    def test_find_components_with_keyword(self):
        """Test finding items by keyword."""
        # Arrange
        with self.get_wanda_session() as model:
            keyword = "PG1"

            # Act
            items = find_items_with_keyword(model, keyword)

            # Assert
            self.assertListEqual(
                [item.name for item in items], ["PUMP P1", "PUMP P2", "PUMP P3"]
            )
            self.assertListEqual([item.type for item in items], ["component"] * 3)

    def test_resolve_items(self):
        """Test resolving items from identifiers."""
        # Arrange
        with self.get_wanda_session() as model:
            identifiers = ["PUMP P2", "H-node G", "Signal A.c", "PG1"]

            # Act
            resolved_items = []
            for identifier in identifiers:
                resolved_items.extend(resolve_items(model, identifier))

            # Assert
            expected_names = [
                "PUMP P2",
                "H-node G",
                "Signal A.c",
                "PUMP P1",
                "PUMP P2",
                "PUMP P3",
            ]
            expected_types = [
                "component",
                "node",
                "signal_line",
                "component",
                "component",
                "component",
            ]

            self.assertListEqual([item.name for item in resolved_items], expected_names)
            self.assertListEqual([item.type for item in resolved_items], expected_types)

    def test_get_item(self):
        """Test retrieving an item by WandaItemRef."""
        # Arrange
        with self.get_wanda_session() as model:
            item_ref_list = [
                WandaItemRef(name="PUMP P2", type="component"),
                WandaItemRef(name="H-node G", type="node"),
                WandaItemRef(name="Signal A.c", type="signal_line"),
            ]

            # Act
            items = [get_item(model, item_ref) for item_ref in item_ref_list]

            # Assert
            self.assertEqual(items[0].get_complete_name_spec(), "PUMP P2")
            self.assertEqual(items[1].get_complete_name_spec(), "H-node G")
            self.assertEqual(items[2].get_complete_name_spec(), "Signal A.c")

    def test_unknown_type_item(self):
        """Test error handling for unknown item type."""
        # Arrange
        with self.get_wanda_session() as model:
            unknown_ref = WandaItemRef(name="UNKNOWN ITEM", type="UNKNOWN")

            # Act & Assert
            with self.assertRaises(ValueError) as context:
                get_item(model, unknown_ref)

                self.assertEqual(str(context.exception), "Unknown item type: UNKNOWN")
                self.assertEqual(context.exception.__class__, ValueError)
