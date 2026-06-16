"""Unit tests for postprocessing.plotting.renderers.combined_report."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from pywandahydra.postprocessing.io.cache import ParquetCache  # noqa: E402
from pywandahydra.postprocessing.plotting.renderers.combined_report import (
    render_combined_report_pages,  # noqa: E402
)
from pywandahydra.postprocessing.plotting.renderers.report_page import ReportMeta  # noqa: E402
from pywandahydra.postprocessing.plotting.renderers.theme import PlotTheme  # noqa: E402
from pywandahydra.scenarios.models.plot_route import RoutePlotSpecification  # noqa: E402
from pywandahydra.scenarios.models.plot_time import TimePlotSpecification  # noqa: E402

BASE_META = ReportMeta(
    case_name="case_001",
    analysis_description="Analysis desc",
    scenario_description="Scenario desc",
    chapter="Chapter 1",
    project_number="12345",
    figure_id="Fig",
    wanda_version="WANDA 4.8",
    report_date="01-01-2026",
)


def _write_route_cache(cache: ParquetCache, title: str) -> None:
    extracted = {
        "components": pd.DataFrame(),
        "routes": {
            title: {
                "envelope": pd.DataFrame(
                    {"min": [1.0, 2.0], "max": [3.0, 4.0]},
                    index=pd.Index([0.0, 10.0], name="s_location [m]"),
                ),
                "profile": pd.DataFrame(
                    {"elevation": [100.0, 110.0]},
                    index=pd.Index([0.0, 10.0], name="s_location [m]"),
                ),
            }
        },
    }
    cache.write(extracted)


def _write_components_cache(cache: ParquetCache) -> None:
    columns = pd.MultiIndex.from_tuples(
        [("PUMP P1", "Head", float("nan"))],
        names=["component", "property", "s_location"],
    )
    components = pd.DataFrame(
        [[1.0], [2.0]], columns=columns, index=pd.Index([0.0, 1.0], name="time [s]")
    )
    cache.write({"components": components, "routes": {}})


class TestRenderCombinedReportPages(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cache = ParquetCache(Path(self.tmp_dir.name))
        self.theme = PlotTheme()
        self._figures: list = []

    def tearDown(self) -> None:
        for fig in self._figures:
            plt.close(fig)
        self.tmp_dir.cleanup()

    def test_empty_specs_returns_empty_list(self) -> None:
        result = render_combined_report_pages([], self.cache, report_meta_base=BASE_META)

        self.assertEqual(result, [])

    def test_single_route_spec_produces_one_figure_with_one_axes(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1)

        figures = render_combined_report_pages(
            [spec], self.cache, report_meta_base=BASE_META, theme=self.theme
        )
        self._figures.extend(figures)

        self.assertEqual(len(figures), 1)
        fig = figures[0]
        # One content axes plus the layout axes (background frame) and
        # the watermark image axes added by draw_layout.
        content_axes = [ax for ax in fig.axes if ax.get_title()]
        self.assertEqual(len(content_axes), 1)
        self.assertEqual(content_axes[0].get_title(), "Route A_Pressure")

    def test_single_time_spec_produces_one_figure_with_plotted_series(self) -> None:
        _write_components_cache(self.cache)
        spec = TimePlotSpecification(component="PUMP P1", property="Head", fig="1", plot=1)

        figures = render_combined_report_pages(
            [spec], self.cache, report_meta_base=BASE_META, theme=self.theme
        )
        self._figures.extend(figures)

        self.assertEqual(len(figures), 1)
        fig = figures[0]
        content_axes = [ax for ax in fig.axes if ax.get_title()]
        self.assertEqual(len(content_axes), 1)
        self.assertEqual(len(content_axes[0].get_lines()), 1)

    def test_multiple_plots_in_one_figure_create_stacked_axes(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        _write_route_cache(self.cache, "Route B_Pressure")
        specs = [
            RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1),
            RoutePlotSpecification(route_id="Route B", property="Pressure", fig="1", plot=2),
        ]

        figures = render_combined_report_pages(
            specs,  # type: ignore[arg-type]  # mypy doesn't know about the list of specs being valid for multiple plots
            self.cache,
            report_meta_base=BASE_META,
            theme=self.theme,
        )
        self._figures.extend(figures)

        self.assertEqual(len(figures), 1)
        content_axes = [ax for ax in figures[0].axes if ax.get_title()]
        self.assertEqual(len(content_axes), 2)
        titles = sorted(ax.get_title() for ax in content_axes)
        self.assertEqual(titles, ["Route A_Pressure", "Route B_Pressure"])

    def test_specs_with_different_fig_keys_produce_multiple_figures(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        _write_route_cache(self.cache, "Route B_Pressure")
        specs = [
            RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1),
            RoutePlotSpecification(route_id="Route B", property="Pressure", fig="2", plot=1),
        ]

        figures = render_combined_report_pages(
            specs,  # type: ignore[arg-type]  # mypy doesn't know about the list of specs being valid for multiple plots
            self.cache,
            report_meta_base=BASE_META,
            theme=self.theme,
        )
        self._figures.extend(figures)

        self.assertEqual(len(figures), 2)

    def test_missing_envelope_skips_panel_and_returns_no_figure(self) -> None:
        # No cache written - envelope lookup returns empty dict.
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1)

        figures = render_combined_report_pages(
            [spec], self.cache, report_meta_base=BASE_META, theme=self.theme
        )
        self._figures.extend(figures)

        self.assertEqual(figures, [])

    def test_missing_component_cache_skips_time_panel(self) -> None:
        # No components cache written.
        spec = TimePlotSpecification(component="PUMP P1", property="Head", fig="1", plot=1)

        with self.assertLogs(
            "pywandahydra.postprocessing.plotting.renderers.combined_report",
            level="WARNING",
        ):
            figures = render_combined_report_pages(
                [spec], self.cache, report_meta_base=BASE_META, theme=self.theme
            )
        self._figures.extend(figures)

        self.assertEqual(figures, [])

    def test_mixed_types_in_one_plot_raises_value_error(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        _write_components_cache(self.cache)
        specs = [
            RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1),
            TimePlotSpecification(component="PUMP P1", property="Head", fig="1", plot=1),
        ]

        with self.assertRaises(ValueError):
            render_combined_report_pages(
                specs,  # type: ignore[arg-type]  # mypy doesn't know about the list of specs being valid for multiple plots
                self.cache,
                report_meta_base=BASE_META,
                theme=self.theme,
            )

    def test_too_many_route_specs_in_one_panel_raises_value_error(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        _write_route_cache(self.cache, "Route B_Pressure")
        specs = [
            RoutePlotSpecification(route_id="Route A", property="Pressure", fig="1", plot=1),
            RoutePlotSpecification(route_id="Route B", property="Pressure", fig="1", plot=1),
        ]

        with self.assertRaises(ValueError):
            render_combined_report_pages(
                specs,  # type: ignore[arg-type]  # mypy doesn't know about the list of specs being valid for multiple plots
                self.cache,
                report_meta_base=BASE_META,
                theme=self.theme,
            )

    def test_figure_id_includes_fig_key_suffix(self) -> None:
        _write_route_cache(self.cache, "Route A_Pressure")
        spec = RoutePlotSpecification(route_id="Route A", property="Pressure", fig="3", plot=1)

        figures = render_combined_report_pages(
            [spec], self.cache, report_meta_base=BASE_META, theme=self.theme
        )
        self._figures.extend(figures)

        # fig_name text is rendered via draw_layout; check the underlying
        # figure text includes the base figure_id + fig_key.
        texts = [t.get_text() for t in figures[0].texts]
        self.assertIn(f"{BASE_META.figure_id}3", texts)


if __name__ == "__main__":
    unittest.main()
