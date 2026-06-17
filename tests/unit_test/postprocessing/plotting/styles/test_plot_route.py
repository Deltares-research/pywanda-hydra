"""Unit tests for the PlotRoute class in route plotting styles."""

import unittest

import matplotlib.pyplot as plt
import numpy as np

from pywandahydra.postprocessing.plotting.models import (
    AxisSpec,
    PlotTextAnnotation,
    RouteData,
    RouteSeries,
)
from pywandahydra.postprocessing.plotting.styles.route_plots import PlotRoute


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

    def test_plot_route_raises_for_mismatched_series_length(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="bad", values=[1, 2])],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
        )
        fig, ax = plt.subplots()

        # Act / Assert
        with self.assertRaises(ValueError):
            plot.plot(ax)

        plt.close(fig)

    def test_plot_route_absolute_values_for_velocity(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[-1, -2, -3])],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Velocity",
            title="Route velocity",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        line = ax.get_lines()[0]
        np.testing.assert_array_equal(line.get_ydata(), [1, 2, 3])

        plt.close(fig)

    def test_plot_route_min_series_uses_dash_dot_linestyle(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="min", values=[1, 2, 3])],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        line = ax.get_lines()[0]
        self.assertEqual(line.get_linestyle(), "-.")

        plt.close(fig)

    def test_plot_route_with_elevation_overlay(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[1, 2, 3])],
            s_location_profile=[0, 10, 20],
            elevation=[5, 6, 7],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            plot_elevation=True,
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        labels = [line.get_label() for line in ax.get_lines()]
        self.assertIn("Elevation", labels)

        plt.close(fig)

    def test_plot_route_elevation_overlay_missing_data_raises(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[1, 2, 3])],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            plot_elevation=True,
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act / Assert
        with self.assertRaises(ValueError):
            plot.plot(ax)

        plt.close(fig)

    def test_plot_route_elevation_overlay_length_mismatch_raises(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[1, 2, 3])],
            s_location_profile=[0, 10, 20],
            elevation=[5, 6],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            plot_elevation=True,
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act / Assert
        with self.assertRaises(ValueError):
            plot.plot(ax)

        plt.close(fig)

    def test_plot_route_text_annotations(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[1, 2, 3])],
            text_annotations=[
                PlotTextAnnotation(x=5, y=1, dx=0.5, dy=0.5, text="Annotation")
            ],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            show_endpoints=False,
        )
        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        texts = [t.get_text() for t in ax.texts]
        self.assertIn("Annotation", texts)
        # marker line plotted in addition to the data series line
        self.assertEqual(len(ax.get_lines()), 2)

        plt.close(fig)

    def test_plot_route_no_endpoint_labels_skips_text(self):
        # Arrange
        route_data = RouteData(
            s_location=[0, 10, 20],
            series=[RouteSeries(label="0 s", values=[1, 2, 3])],
        )
        plot = PlotRoute(
            data=route_data,
            prop="Head",
            title="Route head",
            x_axis=AxisSpec(),
            y_axis=AxisSpec(),
            show_endpoints=True,
        )
        fig, ax = plt.subplots()

        # Act
        plot.plot(ax)

        # Assert
        self.assertEqual(len(ax.texts), 0)

        plt.close(fig)
