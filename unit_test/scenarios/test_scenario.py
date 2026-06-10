from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.scenarios.mapper import ScenarioLoadOptions, load_scenarios
from pywandahydra.scenarios.schema import ScenarioSpecification
from pywandahydra.scenarios.sources.xls import _read_rplots_sheet


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

    def test_rplots_parses_fig_and_plot_columns(self) -> None:
        """Rplots parser should preserve fig/page key and plot/row ordering fields."""
        rplots = pd.DataFrame(
            {
                "title": ["EWL01 - Head profile", "EWL01 - Pressure profile"],
                "name": ["Route_A", "Route_A"],
                "property": ["Head", "Pressure"],
                "fig": ["a", "a"],
                "plot": [1, 2],
                "Xlabel": ["S-distance (m)", "S-distance (m)"],
                "Ylabel": ["Head (m)", "Pressure (barg)"],
            }
        )

        with tempfile.TemporaryDirectory() as td:
            xlsx = Path(td) / "rplots.xlsx"
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                rplots.to_excel(writer, sheet_name="Rplots", index=False)

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].fig, "a")
        self.assertEqual(specs[0].plot, 1)
        self.assertEqual(specs[1].fig, "a")
        self.assertEqual(specs[1].plot, 2)
