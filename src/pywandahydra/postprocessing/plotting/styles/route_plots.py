from __future__ import annotations

import numpy as np
from matplotlib.axes._axes import Axes

from pywandahydra.postprocessing.plotting.schema import RouteData
from pywandahydra.postprocessing.plotting.specifications import AxisSpec

from .plot_object import DataPlot


class PlotRoute(DataPlot[RouteData]):
    """Plot a route-based data series."""

    def __init__(
        self,
        *,
        data: RouteData,
        prop: str,
        title: str,
        x_axis: AxisSpec,
        y_axis: AxisSpec,
        plot_elevation: bool = False,
        show_endpoints: bool = True,
    ):
        """Initialize the route plot.

        Parameters
        ----------
        data : RouteData
            The route data to plot.
        prop : str
            The property being plotted (e.g., "Velocity", "Discharge").
        title : str
            The title of the plot.
        x_axis : AxisSpec
            Specification for the x-axis.
        y_axis : AxisSpec
            Specification for the y-axis.
        plot_elevation : bool, optional
            Whether to overlay the elevation profile, by default False.
        show_endpoints : bool, optional
            Whether to show start and end labels, by default True.
        """
        self.prop = prop
        self.plot_elevation = plot_elevation
        self.show_endpoints = show_endpoints
        super().__init__(data=data, title=title, x_axis=x_axis, y_axis=y_axis)

    def _draw(self, ax: Axes) -> None:
        s = np.asarray(self.data.s_location, dtype=float)

        # Draw each series
        for series in self.data.series:
            y = np.asarray(series.values, dtype=float)
            if len(y) != len(s):
                raise ValueError(
                    f"Route series '{series.label}' has length {len(y)} "
                    f"but s_location has length {len(s)}."
                )

            # Absolute values for certain properties
            if self.prop in ("Velocity", "Discharge"):
                y = np.abs(y)

            # Plot with special styles for min/max
            label = series.label
            if label.lower() == "max":
                ax.plot(s, y, label=label, linestyle="--", zorder=-1)
            elif label.lower() == "min":
                ax.plot(s, y, label=label, linestyle="-.", zorder=-1)
            else:
                ax.plot(s, y, label=label)

        # Optional elevation overlay
        if self.plot_elevation:
            self._draw_elevation(ax)

        # Optional point/text annotations
        for ann in self.data.text_annotations:
            ax.plot(ann.x, ann.y, "ro")
            ax.text(ann.x + ann.dx, ann.y + ann.dy, ann.text)

        # Optional endpoint labels (based on current axes extent)
        if self.show_endpoints:
            self._draw_endpoints(ax)

    def _draw_elevation(self, ax: Axes) -> None:
        """Draw the elevation profile on the plot.

        Parameters
        ----------
        ax : Axes
            The axes on which to draw the elevation profile.
        """
        if self.data.s_location_profile is None or self.data.elevation is None:
            raise ValueError(
                "plot_elevation=True requires s_location_profile and elevation in RouteData."
            )

        sp = np.asarray(self.data.s_location_profile, dtype=float)
        elev = np.asarray(self.data.elevation, dtype=float)

        if len(sp) != len(elev):
            raise ValueError(
                f"Elevation length {len(elev)} does not match s_location_profile length {len(sp)}."
            )

        ax.plot(sp, elev, label="Elevation", linewidth=2, alpha=0.3, zorder=-2)

    def _draw_endpoints(self, ax: Axes) -> None:
        """Draw start and end labels on the plot.

        Parameters
        ----------
        ax : Axes
            The axes on which to draw the endpoint labels.
        """
        if not self.data.start_label and not self.data.end_label:
            return

        # Note: use axes limits (unscaled) and apply factor to match your old behavior
        xmin, xmax = np.array(ax.get_xlim()) / self.x_axis.factor
        ymin, ymax = np.array(ax.get_ylim()) / self.y_axis.factor

        stepx = (xmax - xmin) * 0.05
        stepy = (ymax - ymin) * 0.05

        if self.data.start_label:
            ax.text(xmin + stepx, ymin + stepy, self.data.start_label)
        if self.data.end_label:
            ax.text(xmax - 3 * stepx, ymin + stepy, self.data.end_label)
            ax.text(xmax - 3 * stepx, ymin + stepy, self.data.end_label)
