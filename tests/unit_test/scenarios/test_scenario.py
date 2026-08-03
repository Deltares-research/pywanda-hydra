from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.config.models import ModelSpecification
from pywandahydra.execution.case_plan import build_case_plans
from pywandahydra.scenarios import ScenarioLoadOptions, ScenarioSpecification, load_scenarios
from pywandahydra.scenarios.excel.post_processing import _read_rplots_sheet, _read_tplots_sheet
from pywandahydra.scenarios.loader import load_scenario_document


class TestScenarioLoading(unittest.TestCase):
    def setUp(self) -> None:
        """Define paths for test data."""
        # Data directory
        self.test_dir = Path(__file__).parent
        self.data_dir = Path(self.test_dir.parent.parent, "data", "scenarios")
        self.test_xls_path = Path(self.data_dir, "ExampleParameter.xls")

    def test_load_scenarios_from_xls(self) -> None:
        """Scenario loading keeps valid rows; include filtering is deferred."""
        # Arrange
        options = ScenarioLoadOptions()

        # Act
        scenarios = load_scenarios(self.test_xls_path, options=options)

        # Assert
        self.assertIsInstance(scenarios, list)
        self.assertIsInstance(scenarios[0], ScenarioSpecification)
        included = sum(1 for s in scenarios if s.include)
        self.assertEqual(included, 105)
        self.assertGreaterEqual(len(scenarios), included)

    def test_load_document_keeps_excluded_rows_and_tracks_source_path(self) -> None:
        """ScenarioDocument preserves valid rows and stores workbook source path."""
        with tempfile.TemporaryDirectory() as td:
            workbook = Path(td) / "doc.xlsx"
            cases = pd.DataFrame(
                [
                    ["Number", "Include", "Name", "PIPE P1"],
                    ["My analysis", 77, "2024.1", "Diameter"],
                    [1, 1, "Case A", 0.50],
                    [2, 0, "Case B", 0.75],
                ]
            )
            with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
                cases.to_excel(writer, sheet_name="Cases", index=False, header=False)

            options = ScenarioLoadOptions(
                global_description_col="Number",
                global_wanda_version_col="Name",
                global_project_number_col="Include",
            )
            document = load_scenario_document(workbook, options=options)

        self.assertEqual(document.source_path, workbook)
        self.assertEqual(document.analysis_metadata.analysis_description, "My analysis")
        self.assertEqual(len(document.scenarios), 2)
        self.assertEqual(sum(1 for s in document.scenarios if s.include), 1)

    def test_include_filtering_happens_in_case_plan_builder(self) -> None:
        """Execution selection point keeps only included scenarios."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workbook = root / "doc.xlsx"
            cases = pd.DataFrame(
                [
                    ["Number", "Include", "Name", "PIPE P1"],
                    ["My analysis", 77, "2024.1", "Diameter"],
                    [1, 1, "Case A", 0.50],
                    [2, 0, "Case B", 0.75],
                ]
            )
            with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
                cases.to_excel(writer, sheet_name="Cases", index=False, header=False)

            options = ScenarioLoadOptions(
                global_description_col="Number",
                global_wanda_version_col="Name",
                global_project_number_col="Include",
            )
            document = load_scenario_document(workbook, options=options)

            model_path = root / "base_model.wdi"
            model_path.write_bytes(b"base")
            model_spec = ModelSpecification(
                model_path=model_path,
                wanda_bin=Path(r"c:\wanda\bin"),
                base_model_name="base_model",
                run_steady=False,
                run_unsteady=False,
                reuse_existing_data=False,
            )

            plans = build_case_plans(
                model_spec=model_spec,
                scenarios=list(document.scenarios),
                run_root=root / "run",
            )

        self.assertEqual(len(document.scenarios), 2)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].case_id, "Case A")

    def test_unsupported_extension_raises(self) -> None:
        """Loader rejects unsupported scenario file extensions."""
        with tempfile.TemporaryDirectory() as td:
            unsupported = Path(td) / "scenarios.csv"
            unsupported.write_text("dummy", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scenario_document(unsupported)

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

