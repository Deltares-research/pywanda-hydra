"""Unit tests for postprocessing.plotting.renderers.time_report_page."""

from __future__ import annotations

import unittest

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme  # noqa: E402
from pywandahydra.postprocessing.plotting.renderers.time_report_page import (  # noqa: E402
    _plot_time_series_group,
    _select_columns,
    _warn_duplicate_axis_definitions,
)
from pywandahydra.scenarios.models.plot_time import TimePlotSpecification  # noqa: E402


def _make_components() -> pd.DataFrame:
    columns = pd.MultiIndex.from_tuples(
        [
            ("PUMP P1", "Head", float("nan")),
            ("PIPE P1", "Pressure", 0.0),
            ("PIPE P1", "Pressure", 10.0),
        ],
        names=["component", "property", "s_location"],
    )
    return pd.DataFrame(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        columns=columns,
        index=pd.Index([0.0, 1.0], name="time [s]"),
    )


class TestSelectColumns(unittest.TestCase):
    def test_non_multiindex_columns_returns_empty(self) -> None:
        components = pd.DataFrame({"a": [1.0]})
        spec = TimePlotSpecification(component="PUMP P1", property="Head")

        self.assertEqual(_select_columns(components, spec), [])

    def test_no_matching_columns_returns_empty(self) -> None:
        components = _make_components()
        spec = TimePlotSpecification(component="MISSING", property="Head")

        self.assertEqual(_select_columns(components, spec), [])

    def test_single_match_uses_component_label(self) -> None:
        components = _make_components()
        spec = TimePlotSpecification(component="PUMP P1", property="Head")

        result = _select_columns(components, spec)

        self.assertEqual(len(result), 1)
        col, label = result[0]
        self.assertEqual(col[:2], ("PUMP P1", "Head"))
        self.assertEqual(label, "PUMP P1")

    def test_multiple_s_locations_without_requested_location_returns_all(self) -> None:
        components = _make_components()
        spec = TimePlotSpecification(component="PIPE P1", property="Pressure")

        result = _select_columns(components, spec)

        self.assertEqual(len(result), 2)
        labels = sorted(label for _, label in result)
        self.assertEqual(labels, ["PIPE P1 @ s=0.0 m", "PIPE P1 @ s=10.0 m"])

    def test_requested_location_selects_nearest_column(self) -> None:
        components = _make_components()
        spec = TimePlotSpecification(component="PIPE P1", property="Pressure", location=1.0)

        result = _select_columns(components, spec)

        self.assertEqual(len(result), 1)
        col, label = result[0]
        self.assertEqual(col[2], 0.0)
        self.assertEqual(label, "PIPE P1 @ s=0.0 m")


class TestWarnDuplicateAxisDefinitions(unittest.TestCase):
    def test_no_duplicates_does_not_raise(self) -> None:
        specs = [
            TimePlotSpecification(component="PUMP P1", property="Head", title="Title"),
            TimePlotSpecification(component="PUMP P2", property="Head"),
        ]

        # Should simply log a warning when needed; no exception either way.
        _warn_duplicate_axis_definitions(specs)

    def test_duplicate_titles_logs_warning(self) -> None:
        specs = [
            TimePlotSpecification(component="PUMP P1", property="Head", title="A"),
            TimePlotSpecification(component="PUMP P2", property="Head", title="B"),
        ]

        with self.assertLogs(
            "pywandahydra.postprocessing.plotting.renderers.time_report_page",
            level="WARNING",
        ) as cm:
            _warn_duplicate_axis_definitions(specs)

        self.assertTrue(any("title" in msg for msg in cm.output))


class TestPlotTimeSeriesGroup(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = PlotTheme()
        self.fig, self.ax = plt.subplots()

    def tearDown(self) -> None:
        plt.close(self.fig)

    def test_returns_false_and_logs_warning_when_no_data(self) -> None:
        components = _make_components()
        specs = [TimePlotSpecification(component="MISSING", property="Head")]

        with self.assertLogs(
            "pywandahydra.postprocessing.plotting.renderers.time_report_page",
            level="WARNING",
        ):
            result = _plot_time_series_group(self.ax, specs, components, self.theme)

        self.assertFalse(result)
        self.assertEqual(len(self.ax.get_lines()), 0)

    def test_plots_single_series_with_default_title_and_legend(self) -> None:
        components = _make_components()
        specs = [TimePlotSpecification(component="PUMP P1", property="Head")]

        result = _plot_time_series_group(self.ax, specs, components, self.theme)

        self.assertTrue(result)
        self.assertEqual(len(self.ax.get_lines()), 1)
        self.assertEqual(self.ax.get_title(), "PUMP P1_Head")
        self.assertEqual(self.ax.get_xlabel(), "Time (s)")
        self.assertIsNotNone(self.ax.get_legend())

    def test_plots_multiple_s_location_series_for_pipe(self) -> None:
        components = _make_components()
        specs = [TimePlotSpecification(component="PIPE P1", property="Pressure")]

        result = _plot_time_series_group(self.ax, specs, components, self.theme)

        self.assertTrue(result)
        self.assertEqual(len(self.ax.get_lines()), 2)
        legend_labels = sorted(line.get_label() for line in self.ax.get_lines())
        self.assertEqual(legend_labels, ["PIPE P1 @ s=0.0 m", "PIPE P1 @ s=10.0 m"])

    def test_multiple_specs_combine_onto_one_axes(self) -> None:
        components = _make_components()
        specs = [
            TimePlotSpecification(component="PUMP P1", property="Head", title="Combined"),
            TimePlotSpecification(component="PIPE P1", property="Pressure", location=0.0),
        ]

        result = _plot_time_series_group(self.ax, specs, components, self.theme)

        self.assertTrue(result)
        self.assertEqual(len(self.ax.get_lines()), 2)
        self.assertEqual(self.ax.get_title(), "Combined")

    def test_custom_legend_label_used_when_provided(self) -> None:
        components = _make_components()
        specs = [
            TimePlotSpecification(component="PUMP P1", property="Head", legend="My Pump")
        ]

        _plot_time_series_group(self.ax, specs, components, self.theme)

        labels = [line.get_label() for line in self.ax.get_lines()]
        self.assertEqual(labels, ["My Pump"])


if __name__ == "__main__":
    unittest.main()
