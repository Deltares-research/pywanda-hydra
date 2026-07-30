"""Unit tests for the time-series plot renderer."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import matplotlib.pyplot as plt
import pandas as pd

from pywandahydra.postprocessing.plotting.renderers.time_series import render_time_series_plot
from pywandahydra.scenarios.models.plot_axis import AxisSpecification


class TestRenderTimeSeriesPlot(unittest.TestCase):
    def _make_cache(self, df: pd.DataFrame) -> MagicMock:
        cache = MagicMock()
        cache.read_components.return_value = df
        return cache

    def test_returns_none_for_empty_cache(self) -> None:
        # Arrange
        cache = self._make_cache(pd.DataFrame())

        # Act
        fig = render_time_series_plot(["Pipe1"], "Discharge", cache)

        # Assert
        self.assertIsNone(fig)

    def test_returns_none_when_no_matching_data(self) -> None:
        # Arrange
        columns = pd.MultiIndex.from_tuples(
            [("Pipe1", "Velocity", float("nan"))],
            names=["component", "property", "s_location"],
        )
        df = pd.DataFrame({columns[0]: [1.0, 2.0, 3.0]}, index=[0, 1, 2])
        cache = self._make_cache(df)

        # Act
        fig = render_time_series_plot(["Pipe1"], "Discharge", cache)

        # Assert
        self.assertIsNone(fig)

    def test_renders_multiindex_columns_without_s_location(self) -> None:
        # Arrange
        columns = pd.MultiIndex.from_tuples(
            [("Pipe1", "Discharge", float("nan"))],
            names=["component", "property", "s_location"],
        )
        df = pd.DataFrame({columns[0]: [1.0, 2.0, 3.0]}, index=[0.0, 1.0, 2.0])
        cache = self._make_cache(df)

        # Act
        fig = render_time_series_plot(["Pipe1"], "Discharge", cache)

        # Assert
        self.assertIsNotNone(fig)
        ax = fig.axes[0]  # type: ignore[union-attr]
        self.assertEqual(len(ax.get_lines()), 1)
        legend = ax.get_legend()
        legend_labels = [t.get_text() for t in legend.get_texts()]  # type: ignore[union-attr]
        self.assertEqual(legend_labels, ["Pipe1"])
        self.assertEqual(ax.get_xlabel(), "Time [s]")
        self.assertEqual(ax.get_title(), "Discharge")

        plt.close(fig)

    def test_renders_multiindex_columns_with_s_location(self) -> None:
        # Arrange
        columns = pd.MultiIndex.from_tuples(
            [("Pipe1", "Discharge", 12.5)],
            names=["component", "property", "s_location"],
        )
        df = pd.DataFrame({columns[0]: [1.0, 2.0, 3.0]}, index=[0.0, 1.0, 2.0])
        cache = self._make_cache(df)

        # Act
        fig = render_time_series_plot(["Pipe1"], "Discharge", cache)

        # Assert
        ax = fig.axes[0]  # type: ignore[union-attr]
        legend = ax.get_legend()
        legend_labels = [t.get_text() for t in legend.get_texts()]  # type: ignore[union-attr]
        self.assertEqual(legend_labels, ["Pipe1 s=12.5 m"])

        plt.close(fig)

    def test_renders_flat_columns(self) -> None:
        # Arrange
        df = pd.DataFrame({"Pipe1|Discharge": [1.0, 2.0, 3.0]}, index=[0.0, 1.0, 2.0])
        cache = self._make_cache(df)

        # Act
        fig = render_time_series_plot(["Pipe1"], "Discharge", cache)

        # Assert
        ax = fig.axes[0]  # type: ignore[union-attr]
        self.assertEqual(len(ax.get_lines()), 1)
        legend = ax.get_legend()
        legend_labels = [t.get_text() for t in legend.get_texts()]  # type: ignore[union-attr]
        self.assertEqual(legend_labels, ["Pipe1"])

        plt.close(fig)

    def test_applies_axis_specs_and_custom_title(self) -> None:
        # Arrange
        df = pd.DataFrame({"Pipe1|Discharge": [1.0, 2.0, 3.0]}, index=[0.0, 1.0, 2.0])
        cache = self._make_cache(df)
        x_axis = AxisSpecification(label="Time [h]")
        y_axis = AxisSpecification(label="Discharge [m3/s]")

        # Act
        fig = render_time_series_plot(
            ["Pipe1"],
            "Discharge",
            cache,
            title="Custom title",
            x_axis=x_axis,
            y_axis=y_axis,
        )

        # Assert
        ax = fig.axes[0]  # type: ignore[union-attr]
        self.assertEqual(ax.get_xlabel(), "Time [h]")
        self.assertEqual(ax.get_ylabel(), "Discharge [m3/s]")
        self.assertEqual(ax.get_title(), "Custom title")

        plt.close(fig)

    def test_saves_figure_when_output_dir_provided(self) -> None:
        # Arrange
        import tempfile
        from pathlib import Path

        df = pd.DataFrame({"Pipe1|Discharge": [1.0, 2.0, 3.0]}, index=[0.0, 1.0, 2.0])
        cache = self._make_cache(df)

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Act
            fig = render_time_series_plot(
                ["Pipe1"],
                "Discharge",
                cache,
                output_dir=Path(tmp_dir),
                filename="my_plot",
            )

            # Assert
            self.assertTrue((Path(tmp_dir) / "my_plot.pdf").exists())

        # fig was closed by savefig
        self.assertFalse(plt.fignum_exists(fig.number))  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
