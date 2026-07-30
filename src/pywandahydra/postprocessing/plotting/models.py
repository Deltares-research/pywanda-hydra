"""Compatibility re-exports for plot axis/annotation models.

The canonical definitions live in ``pywandahydra.scenarios.models.plot_axis``.
"""

from __future__ import annotations

from pywandahydra.scenarios.models.plot_axis import AxisSpecification, PlotTextAnnotation

AxisSpec = AxisSpecification

__all__ = ["AxisSpecification", "AxisSpec", "PlotTextAnnotation"]
