"""Unit tests for the PlotRoute class in route plotting styles."""

import unittest

import matplotlib
import matplotlib.pyplot as plt

from pywandahydra.postprocessing.plotting.schema import RouteData, RouteSeries
from pywandahydra.postprocessing.plotting.specifications import AxisSpec
from pywandahydra.postprocessing.plotting.styles.route_plots import PlotRoute

matplotlib.use("Agg")  # headless backend for CI / unit tests


class TestPlotRoute(unittest.TestCase):
    def test_plot_route_renders_lines_and_labels(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[
                RouteSeries(label="0 s", values=[10, 11, 12]),
                RouteSeries(label="max", values=[12, 13, 14]),
            ],
            start_label="Pipe start",
            end_label="Pipe end",
        )

        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(label="Distance [m]", factor=1.0),
            y_axis=AxisSpec(label="Head [m]", factor=1.0),
            plot_elevation=False,
        )

        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        # - Ensure lines and labels are rendered correctly
        self.assertEqual(len(ax.get_lines()), 2)
        self.assertEqual(ax.get_title(), "Route head")
        self.assertEqual(ax.get_xlabel(), "Distance [m]")
        self.assertEqual(ax.get_ylabel(), "Head [m]")

        # - Ensure correct legend and text annotations
        legend = ax.get_legend()
        self.assertIsNotNone(legend)
        legend_labels = [t.get_text() for t in legend.get_texts()]
        self.assertIn("0 s", legend_labels)
        self.assertIn("max", legend_labels)

        # - Ensure start and end labels are present
        texts = [t.get_text() for t in ax.texts]
        self.assertIn("Pipe start", texts)
        self.assertIn("Pipe end", texts)

        plt.close(fig)
