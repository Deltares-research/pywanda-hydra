"""Unit tests for postprocessing.plotting.renderers.report_page."""

from __future__ import annotations

import unittest
from datetime import datetime


import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pywandahydra.postprocessing.plotting.renderers.report_page import (  # noqa: E402
    ReportMeta,
    _annotate_pipe_boundaries,
    _create_content_axes,
    _extract_profile_series,
    _extract_time_zero_series,
    _parse_report_date,
    _plot_route_series,
    _to_page_metadata,
)
from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme  # noqa: E402
from pywandahydra.scenarios.models.plot_route import RoutePlotSpecification  # noqa: E402


def _make_envelope() -> pd.DataFrame:
    return pd.DataFrame(
        {"min": [1.0, 0.5, 2.0], "max": [5.0, 6.0, 4.0]},
        index=pd.Index([10.0, 0.0, 20.0], name="s_location [m]"),
    )


def _make_timeseries_columns(component_labels: list[tuple[str, float]]) -> pd.MultiIndex:
    return pd.MultiIndex.from_tuples(
        [(label, "Pressure", s) for label, s in component_labels],
        names=["component", "property", "s_location"],
    )


class TestCreateContentAxes(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = PlotTheme()
        self.fig = plt.figure(figsize=self.theme.figure_size)

    def tearDown(self) -> None:
        plt.close(self.fig)

    def test_zero_count_returns_empty_list(self) -> None:
        axes = _create_content_axes(self.fig, 0, self.theme)

        self.assertEqual(axes, [])

    def test_single_axis_spans_content_area(self) -> None:
        axes = _create_content_axes(self.fig, 1, self.theme)

        self.assertEqual(len(axes), 1)
        box = axes[0].get_position()
        self.assertAlmostEqual(box.x0, self.theme.content_left)
        self.assertAlmostEqual(box.width, self.theme.content_right - self.theme.content_left)

    def test_multiple_axes_are_stacked_vertically(self) -> None:
        axes = _create_content_axes(self.fig, 3, self.theme)

        self.assertEqual(len(axes), 3)
        # Each axes should be added to the figure.
        self.assertEqual(len(self.fig.axes), 3)
        # Top axes should sit above the bottom axes (higher y0).
        y0_values = [ax.get_position().y0 for ax in axes]
        self.assertEqual(y0_values, sorted(y0_values, reverse=True))


class TestPlotRouteSeries(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = PlotTheme()
        self.fig, self.ax = plt.subplots()

    def tearDown(self) -> None:
        plt.close(self.fig)

    def test_plots_min_max_envelope_with_labels(self) -> None:
        spec = RoutePlotSpecification(
            route_id="Route A", property="Pressure", title="Route A pressure"
        )
        envelope = _make_envelope()
        route_data: dict[str, pd.DataFrame] = {}

        _plot_route_series(self.ax, spec, envelope, route_data, self.theme)

        labels = [line.get_label() for line in self.ax.get_lines()]
        self.assertIn("min", labels)
        self.assertIn("max", labels)
        self.assertEqual(self.ax.get_title(), "Route A pressure")

    def test_default_title_uses_route_id_and_property(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure")
        envelope = _make_envelope()

        _plot_route_series(self.ax, spec, envelope, {}, self.theme)

        self.assertEqual(self.ax.get_title(), "Route A_Pressure")

    def test_default_xlabel_set_when_axis_spec_has_no_label(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure")
        envelope = _make_envelope()

        _plot_route_series(self.ax, spec, envelope, {}, self.theme)

        self.assertEqual(self.ax.get_xlabel(), "S-distance (m)")

    def test_head_property_plots_elevation_profile(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Head")
        envelope = _make_envelope()
        profile = pd.DataFrame(
            {"elevation": [100.0, 110.0, 105.0]},
            index=pd.Index([0.0, 10.0, 20.0], name="s_location [m]"),
        )
        route_data = {"profile": profile}

        _plot_route_series(self.ax, spec, envelope, route_data, self.theme)

        labels = [line.get_label() for line in self.ax.get_lines()]
        self.assertIn("Elevation", labels)

    def test_non_head_property_does_not_plot_elevation_profile(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure")
        envelope = _make_envelope()
        profile = pd.DataFrame(
            {"elevation": [100.0, 110.0, 105.0]},
            index=pd.Index([0.0, 10.0, 20.0], name="s_location [m]"),
        )
        route_data = {"profile": profile}

        _plot_route_series(self.ax, spec, envelope, route_data, self.theme)

        labels = [line.get_label() for line in self.ax.get_lines()]
        self.assertNotIn("Elevation", labels)

    def test_zero_second_series_plotted_when_timeseries_cached(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure")
        envelope = _make_envelope()
        columns = _make_timeseries_columns([("PIPE P1", 0.0), ("PIPE P1", 10.0)])
        timeseries = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns, index=[0.0, 1.0])
        route_data = {"timeseries": timeseries}

        _plot_route_series(self.ax, spec, envelope, route_data, self.theme)

        labels = [line.get_label() for line in self.ax.get_lines()]
        self.assertIn("0 s", labels)

    def test_legend_created_for_route_subplot(self) -> None:
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure")
        envelope = _make_envelope()

        _plot_route_series(self.ax, spec, envelope, {}, self.theme)

        legend = self.ax.get_legend()
        self.assertIsNotNone(legend)


class TestAnnotatePipeBoundaries(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = PlotTheme()
        self.fig, self.ax = plt.subplots()

    def tearDown(self) -> None:
        plt.close(self.fig)

    def test_draws_dashed_line_at_interior_boundary_only(self) -> None:
        columns = _make_timeseries_columns(
            [("PIPE P1", 0.0), ("PIPE P1", 10.0), ("PIPE P2", 10.0), ("PIPE P2", 20.0)]
        )
        timeseries = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]], columns=columns, index=[0.0])
        route_data = {"timeseries": timeseries}
        self.ax.set_xlim(0.0, 20.0)

        _annotate_pipe_boundaries(self.ax, route_data, self.theme)

        lines = [
            line
            for line in self.ax.lines
            if line.get_linestyle() == "--"
            and line.get_color() == "black"
            and line.get_alpha() == 0.5
        ]
        x_values = sorted(line.get_xdata()[0] for line in lines)  # type: ignore[type-var, index]
        # Only the shared boundary between the two pipes is drawn; the
        # overall route start (0.0) and end (20.0) are skipped.
        self.assertEqual(x_values, [10.0])

    def test_labels_each_pipe_centered_on_its_range(self) -> None:
        columns = _make_timeseries_columns(
            [("PIPE P1", 0.0), ("PIPE P1", 10.0), ("PIPE P2", 10.0), ("PIPE P2", 20.0)]
        )
        timeseries = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]], columns=columns, index=[0.0])
        route_data = {"timeseries": timeseries}
        self.ax.set_xlim(0.0, 20.0)

        _annotate_pipe_boundaries(self.ax, route_data, self.theme)

        text_positions = {t.get_text(): t.get_position()[0] for t in self.ax.texts}
        self.assertEqual(text_positions["PIPE P1"], 5.0)
        self.assertEqual(text_positions["PIPE P2"], 15.0)

    def test_no_lines_when_timeseries_missing(self) -> None:
        _annotate_pipe_boundaries(self.ax, {}, self.theme)

        self.assertEqual(len(self.ax.lines), 0)
        self.assertEqual(len(self.ax.texts), 0)

    def test_no_lines_when_timeseries_empty(self) -> None:
        _annotate_pipe_boundaries(self.ax, {"timeseries": pd.DataFrame()}, self.theme)

        self.assertEqual(len(self.ax.lines), 0)
        self.assertEqual(len(self.ax.texts), 0)


class TestExtractTimeZeroSeries(unittest.TestCase):
    def test_returns_none_when_timeseries_missing(self) -> None:
        self.assertIsNone(_extract_time_zero_series({}))

    def test_returns_none_when_timeseries_empty(self) -> None:
        empty = pd.DataFrame()
        self.assertIsNone(_extract_time_zero_series({"timeseries": empty}))

    def test_returns_series_for_multiindex_timeseries(self) -> None:
        columns = _make_timeseries_columns([("PIPE P1", 0.0), ("PIPE P1", 10.0)])
        ts = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns, index=[0.0, 1.0])

        result = _extract_time_zero_series({"timeseries": ts})

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(sorted(result.index), [0.0, 10.0])


class TestExtractProfileSeries(unittest.TestCase):
    def test_returns_none_when_profile_missing(self) -> None:
        s, elev = _extract_profile_series({})

        self.assertIsNone(s)
        self.assertIsNone(elev)

    def test_returns_sorted_profile_arrays(self) -> None:
        profile = pd.DataFrame(
            {"elevation": [110.0, 100.0]},
            index=pd.Index([10.0, 0.0], name="s_location [m]"),
        )

        s, elev = _extract_profile_series({"profile": profile})

        assert s is not None
        assert elev is not None
        np.testing.assert_array_equal(s, [0.0, 10.0])
        np.testing.assert_array_equal(elev, [100.0, 110.0])


class TestToPageMetadata(unittest.TestCase):
    def test_maps_report_meta_to_page_metadata(self) -> None:
        theme = PlotTheme()
        meta = ReportMeta(
            case_name="case_001",
            analysis_description="Analysis desc",
            scenario_description="Scenario desc",
            chapter="Chapter 1",
            project_number="12345",
            figure_id="Fig1",
            wanda_version="WANDA 4.8",
            report_date="01-01-2026",
        )

        page_meta = _to_page_metadata(meta, theme)

        self.assertEqual(page_meta.title, "Fig1")
        self.assertEqual(page_meta.case_title, "Analysis desc")
        self.assertIn("Scenario desc", page_meta.case_description)
        self.assertIn("case_001", page_meta.case_description)
        self.assertEqual(page_meta.proj_number, "12345")
        self.assertEqual(page_meta.section_name, "Chapter 1")
        self.assertEqual(page_meta.fig_name, "Fig1")
        self.assertEqual(page_meta.software_version, "WANDA 4.8")
        self.assertEqual(page_meta.date, datetime(2026, 1, 1))
        self.assertEqual(page_meta.fontsize, theme.footer_fontsize)
        self.assertEqual(page_meta.font_family, theme.footer_font)
        self.assertEqual(page_meta.watermark_alpha, theme.logo_alpha)

    def test_falls_back_to_case_name_and_dashes_when_missing(self) -> None:
        theme = PlotTheme()
        meta = ReportMeta(
            case_name="case_001",
            analysis_description="",
            scenario_description="",
            chapter="",
            project_number="",
            figure_id="",
            wanda_version="",
            report_date="",
        )

        page_meta = _to_page_metadata(meta, theme)

        self.assertEqual(page_meta.title, "figure")
        self.assertEqual(page_meta.case_title, "case_001")
        self.assertEqual(page_meta.case_description, "case_001")
        self.assertEqual(page_meta.proj_number, "-")
        self.assertEqual(page_meta.section_name, "")
        self.assertEqual(page_meta.fig_name, "-")
        self.assertEqual(page_meta.software_version, "WANDA")
        self.assertIsNone(page_meta.date)


class TestParseReportDate(unittest.TestCase):
    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(_parse_report_date(""))

    def test_blank_string_returns_none(self) -> None:
        self.assertIsNone(_parse_report_date("   "))

    def test_parses_dd_mm_yyyy(self) -> None:
        self.assertEqual(_parse_report_date("31-01-2026"), datetime(2026, 1, 31))

    def test_parses_yyyy_mm_dd(self) -> None:
        self.assertEqual(_parse_report_date("2026-01-31"), datetime(2026, 1, 31))

    def test_parses_yyyy_slash_mm_slash_dd(self) -> None:
        self.assertEqual(_parse_report_date("2026/01/31"), datetime(2026, 1, 31))

    def test_parses_dd_slash_mm_slash_yyyy(self) -> None:
        self.assertEqual(_parse_report_date("31/01/2026"), datetime(2026, 1, 31))

    def test_unrecognized_format_returns_none(self) -> None:
        self.assertIsNone(_parse_report_date("not a date"))


if __name__ == "__main__":
    unittest.main()
