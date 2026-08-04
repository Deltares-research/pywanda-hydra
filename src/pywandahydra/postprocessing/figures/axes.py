"""Shared axis configuration for figure renderers."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from pywandahydra.scenarios.models.plot_axis import AxisSpecification


def configure_matplotlib_defaults() -> None:
    """Apply module-level matplotlib defaults for post-processing plots."""
    plt.rcParams.update({"axes.xmargin": 0.0})


def apply_axis_spec(ax: Axes, spec: AxisSpecification, *, axis: str) -> None:
    """Apply an AxisSpecification to a matplotlib Axes."""
    if axis == "x":
        if spec.label:
            ax.set_xlabel(spec.label)
        if spec.min is not None:
            ax.set_xlim(left=spec.min)
        if spec.max is not None:
            ax.set_xlim(right=spec.max)
    else:
        if spec.label:
            ax.set_ylabel(spec.label)
        if spec.min is not None:
            ax.set_ylim(bottom=spec.min)
        if spec.max is not None:
            ax.set_ylim(top=spec.max)
