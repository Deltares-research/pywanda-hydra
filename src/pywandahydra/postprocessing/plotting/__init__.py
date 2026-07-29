"""Plotting package public entry points.

This package contains rendering utilities, plotting models, and theme
registry helpers used by post-processing workflows.
"""

from .models import AxisSpec, PlotTextAnnotation
from .theme_registry import bootstrap, get_theme, list_themes, register_theme

__all__ = [
    "AxisSpec",
    "PlotTextAnnotation",
    "bootstrap",
    "get_theme",
    "list_themes",
    "register_theme",
]
