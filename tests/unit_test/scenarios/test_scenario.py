from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.scenarios.mapper import ScenarioLoadOptions, load_scenarios
from pywandahydra.scenarios.schema import ScenarioSpecification
from pywandahydra.scenarios.sources.xls import _read_rplots_sheet, _read_tplots_sheet


class TestScenarioLoading(unittest.TestCase):
    def setUp(self) -> None:
        """Define paths for test data."""
        # Data directory
        self.test_dir = Path(__file__).parent
        self.data_dir = Path(self.test_dir.parent.parent, "data", "scenarios")
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

    def test_rplots_required_columns_case_insensitive(self) -> None:
        """Rplots parser should accept Title/Name/Property capitalization variants."""
        rplots = pd.DataFrame(
            {
                "Title": ["Route C - Head"],
                "Name": ["Route_C"],
                "Property": ["Head"],
                "Fig": ["c"],
                "Plot": [1],
                "Xlabel": ["S-distance (m)"],
                "Ylabel": ["Head (m)"],
            }
        )

        with tempfile.TemporaryDirectory() as td:
            xlsx = Path(td) / "rplots_caps.xlsx"
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                rplots.to_excel(writer, sheet_name="Rplots", index=False)

            specs = _read_rplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].route_id, "Route_C")
        self.assertEqual(specs[0].property, "Head")
        self.assertEqual(specs[0].fig, "c")
        self.assertEqual(specs[0].plot, 1)

    def test_tplots_parses_styling_and_location_columns(self) -> None:
        """Tplots parser should preserve style metadata in dedicated time-plot specs."""
        tplots = pd.DataFrame(
            {
                "title": ["Node pressure over time"],
                "name": ["PIPE-001"],
                "property": ["Pressure"],
                "fig": ["t1"],
                "plot": [3],
                "location": [125.5],
                "color": ["#336699"],
                "style": ["--"],
                "marker": ["o"],
                "Xlabel": ["t [s]"],
                "Ylabel": ["P [bar]"],
            }
        )

        with tempfile.TemporaryDirectory() as td:
            xlsx = Path(td) / "tplots.xlsx"
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                tplots.to_excel(writer, sheet_name="Tplots", index=False)

            specs = _read_tplots_sheet(xlsx, ScenarioLoadOptions())

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].component, "PIPE-001")
        self.assertEqual(specs[0].property, "Pressure")
        self.assertEqual(specs[0].fig, "t1")
        self.assertEqual(specs[0].plot, 3)
        self.assertEqual(specs[0].location, 125.5)
        self.assertEqual(specs[0].color, "#336699")
        self.assertEqual(specs[0].style, "--")
        self.assertEqual(specs[0].marker, "o")
