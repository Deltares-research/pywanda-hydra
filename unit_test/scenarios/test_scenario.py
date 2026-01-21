from __future__ import annotations

import unittest
from pathlib import Path

from pywandahydra.scenarios.mapper import ScenarioLoadOptions, load_scenarios
from pywandahydra.scenarios.schema import ScenarioSpecification


class TestScenarioLoading(unittest.TestCase):
    def setUp(self) -> None:
        """Define paths for test data."""
        # Data directory
        self.test_dir = Path(__file__).parent
        self.data_dir = Path(self.test_dir.parent.parent, "test_data", "scenarios")
        self.test_xls_path = Path(self.data_dir, "ExampleParameter.xls")

    def test_load_scenarios_from_xls(self) -> None:
        """Test loading scenarios from an XLS file."""
        # Arrange
        options = ScenarioLoadOptions()

        # Act
        scenarios = load_scenarios(self.test_xls_path, options=options)

        print(scenarios)

        # Assert
        self.assertIsInstance(scenarios, list)
        self.assertIsInstance(scenarios[0], ScenarioSpecification)
        self.assertEqual(len(scenarios), 105)  # Expected number of scenarios
