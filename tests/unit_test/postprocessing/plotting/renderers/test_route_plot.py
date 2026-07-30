"""Unit tests for the route plot renderer."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import matplotlib.pyplot as plt
import pandas as pd

from pywandahydra.postprocessing.plotting.renderers.route_plot import render_route_plot
from pywandahydra.scenarios.models.plot_axis import AxisSpecification
from pywandahydra.scenarios.models.plot_route import RoutePlotSpecification


class TestRenderRoutePlot(unittest.TestCase):
    def _make_cache(self, route_data: dict) -> MagicMock:
        cache = MagicMock()
        cache.read_route.return_value = route_data
        return cache

    def _make_spec(self, **overrides) -> RoutePlotSpecification:
        kwargs = dict(route_id="Pipe1", property="Discharge")
        kwargs.update(overrides)
        return RoutePlotSpecification(**kwargs)  # type: ignore[arg-type]

    def test_returns_none_when_no_envelope(self) -> None:
        # Arrange
        cache = self._make_cache({})
        spec = self._make_spec()

        # Act
        fig = render_route_plot(spec, cache)

        # Assert
        self.assertIsNone(fig)

    def test_returns_none_when_envelope_empty(self) -> None:
        # Arrange
        cache = self._make_cache({"envelope": pd.DataFrame()})
        spec = self._make_spec()

        # Act
        fig = render_route_plot(spec, cache)

        # Assert
        self.assertIsNone(fig)

    def test_renders_envelope_with_min_and_max(self) -> None:
        # Arrange
        envelope = pd.DataFrame(
            {"min": [1.0, 2.0, 3.0], "max": [4.0, 5.0, 6.0]},
            index=pd.Index([20.0, 0.0, 10.0], name="s_location [m]"),
        )
        cache = self._make_cache({"envelope": envelope})
        spec = self._make_spec()

        # Act
        fig = render_route_plot(spec, cache)

        # Assert
        self.assertIsNotNone(fig)
        ax = fig.axes[0]  # type: ignore[union-attr]

        legend = ax.get_legend()
        legend_labels = [t.get_text() for t in legend.get_texts()]  # type: ignore[union-attr]
        self.assertIn("min", legend_labels)
        self.assertIn("max", legend_labels)

        # Two plotted lines (min, max)
        self.assertEqual(len(ax.get_lines()), 2)

        # fill_between adds a PolyCollection for the envelope
        self.assertEqual(len(ax.collections), 1)

        # Default x label and title
        self.assertEqual(ax.get_xlabel(), "s_location [m]")
        self.assertEqual(ax.get_title(), "Pipe1_Discharge")

        # Lines sorted by s_location
        line = ax.get_lines()[0]
        self.assertEqual(list(line.get_xdata()), [0.0, 10.0, 20.0])  # type: ignore[arg-type]

        plt.close(fig)

    def test_renders_only_min_column(self) -> None:
        # Arrange
        envelope = pd.DataFrame(
            {"min": [1.0, 2.0, 3.0]},
            index=pd.Index([0.0, 10.0, 20.0], name="s_location [m]"),
        )
        cache = self._make_cache({"envelope": envelope})
        spec = self._make_spec()

        # Act
        fig = render_route_plot(spec, cache)

        # Assert
        ax = fig.axes[0]  # type: ignore[union-attr]
        legend = ax.get_legend()
        legend_labels = [t.get_text() for t in legend.get_texts()]  # type: ignore[union-attr]
        self.assertEqual(legend_labels, ["min"])
        # No fill_between when max column missing
        self.assertEqual(len(ax.collections), 0)

        plt.close(fig)

    def test_uses_custom_title_and_axis_labels(self) -> None:
        # Arrange
        envelope = pd.DataFrame(
            {"min": [1.0, 2.0], "max": [3.0, 4.0]},
            index=pd.Index([0.0, 10.0], name="s_location [m]"),
        )
        cache = self._make_cache({"envelope": envelope})
        spec = self._make_spec(
            title="Custom Title",
            x_axis=AxisSpecification(label="Distance [m]"),
            y_axis=AxisSpecification(label="Discharge [m3/s]"),
        )

        # Act
        fig = render_route_plot(spec, cache)

        # Assert
        ax = fig.axes[0]  # type: ignore[union-attr]
        self.assertEqual(ax.get_title(), "Custom Title")
        self.assertEqual(ax.get_xlabel(), "Distance [m]")
        self.assertEqual(ax.get_ylabel(), "Discharge [m3/s]")

        plt.close(fig)

    def test_saves_figure_when_output_dir_provided(self) -> None:
        # Arrange
        import tempfile
        from pathlib import Path

        envelope = pd.DataFrame(
            {"min": [1.0, 2.0], "max": [3.0, 4.0]},
            index=pd.Index([0.0, 10.0], name="s_location [m]"),
        )
        cache = self._make_cache({"envelope": envelope})
        spec = self._make_spec()

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Act
            fig = render_route_plot(spec, cache, output_dir=Path(tmp_dir), filename="route_fig")

            # Assert
            self.assertTrue((Path(tmp_dir) / "route_fig.pdf").exists())

        self.assertFalse(plt.fignum_exists(fig.number))  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
