"""Unit test for model IO functions."""

import unittest
from pathlib import Path

from pywandahydra.wanda.create_scenario import prepare_scenario_model


class TestModelIO(unittest.TestCase):
    """Unit tests for model IO functions."""

    def test_prepare_scenario_model(self):
        """Test preparing a scenario-specific model."""
        base_model_path = Path(__file__).parents[2] / "test_data" / "wanda" / "base_model.wdi"
        scenario_dir = Path(__file__).parents[2] / "test_data" / "wanda" / "scenarios"
        scenario_name = "test_scenario"

        # Prepare scenario model
        scenario_model_path = prepare_scenario_model(
            base_model_path=base_model_path,
            scenario_dir=scenario_dir,
            scenario_name=scenario_name,
            readonly=False,
        )

        expected_wdi = scenario_dir / f"base_model_{scenario_name}.wdi"
        expected_wdx = scenario_dir / f"base_model_{scenario_name}.wdx"

        # Check if files are created
        self.assertTrue(Path(scenario_model_path).exists())
        self.assertTrue(expected_wdi.exists())
        self.assertTrue(expected_wdx.exists())

        # Clean up created files
        expected_wdi.unlink()
        expected_wdx.unlink()

        # Clean up scenario directory if empty
        try:
            scenario_dir.rmdir()
        except OSError:
            pass  # Directory not empty
