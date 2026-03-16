from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import numpy as np
from matplotlib.axes._axes import Axes
from pydantic import BaseModel

from pywandahydra.postprocessing.plotting.specifications import AxisSpec


class PlotObject(ABC):
    """Base class for plot objects."""

    def __init__(
        self,
        *,
        title: str,
        x_axis: AxisSpec,
        y_axis: AxisSpec,
    ):
        """Initialize the plot object.

        Parameters
        ----------
        title : str
            The title of the plot.
        x_axis : AxisSpec
            Specification for the x-axis.
        y_axis : AxisSpec
            Specification for the y-axis.
        """
        self.title = title

        self.x_axis = x_axis
        self.y_axis = y_axis

    @abstractmethod
    def plot(self, ax: Axes) -> None:
        """Render the plot on the given axes.

        Parameters
        ----------
        ax : Axes
            The axes on which to render the plot.
        """

    def _plot_finish(self, ax: Axes) -> None:
        """Finish plot layout and scaling.

        Parameters
        ----------
        ax : Axes
            The axes on which to finalize the plot.
        """

        # Tight autoscaling on x
        ax.autoscale(tight=True, axis="x")

        # Apply scaling to plotted data
        for line in ax.get_lines():
            x, y = line.get_data()
            line.set_data(
                np.asarray(x) / self.x_axis.factor,
                np.asarray(y) / self.y_axis.factor,
            )

        # Determine axis limits after scaling
        xmin, xmax = np.array(ax.get_xlim()) / self.x_axis.factor
        ymin, ymax = np.array(ax.get_ylim()) / self.y_axis.factor

        # Prevent degenerate y-range
        if (ymax - ymin) < 1:
            ymin = ymin * 0.9
            ymax = ymax * 1.1

        # Override limits if explicitly provided
        ax.set_xlim(
            self.x_axis.min if self.x_axis.min is not None else xmin,
            self.x_axis.max if self.x_axis.max is not None else xmax,
        )
        ax.set_ylim(
            self.y_axis.min if self.y_axis.min is not None else ymin,
            self.y_axis.max if self.y_axis.max is not None else ymax,
        )

        # Labels and title
        ax.set_xlabel(self.x_axis.label)
        ax.set_ylabel(self.y_axis.label)
        ax.set_title(self.title)

        # Grid
        ax.grid(True, linestyle="--", alpha=0.7)

        # Legend below axis
        box = ax.get_position()
        shrink = 0.05
        ax.set_position([box.x0, box.y0 + shrink, box.width, box.height - shrink])
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -shrink / box.height),
            fancybox=True,
            shadow=True,
            ncol=5,
            frameon=True,
        )


TData = TypeVar("TData", bound=BaseModel)


class DataPlot(PlotObject, Generic[TData]):
    """Base class for data-driven plots."""

    def __init__(self, *, data: TData, title: str, x_axis: AxisSpec, y_axis: AxisSpec):
        self.data = data
        super().__init__(title=title, x_axis=x_axis, y_axis=y_axis)

    def plot(self, ax: Axes) -> None:
        """Render the plot on the given axes."""
        self._draw(ax)
        self._plot_finish(ax)

    @abstractmethod
    def _draw(self, ax: Axes) -> None:
        """Draw the plot data on the given axes.

        Parameters
        ----------
        ax : Axes
            The axes on which to draw the plot data.
        """
