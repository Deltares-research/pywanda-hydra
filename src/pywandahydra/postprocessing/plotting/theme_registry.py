"""Theme registry for plotting themes."""

from __future__ import annotations

import logging

from .renderers.theme import PlotTheme

logger = logging.getLogger(__name__)

DEFAULT_THEME = PlotTheme()
# Deltares light theme: uses lighter colors and Deltares house style
DELTARES_LIGHT = PlotTheme(
    min_color="#000000",  # Zwart
    max_color="#FF960D",  # Academy orange (for high values - warning color)
    current_color="#0D38E0",  # Blauw (for current state)
    elevation_color="#00E6A1",  # Lichtgroen (lighter for visibility)
    envelope_alpha=0.15,  # Slightly more visible
    logo_alpha=0.20,  # Slightly more visible
)

_THEMES: dict[str, PlotTheme] = {}


def register_theme(name: str, theme: PlotTheme) -> None:
    """Register a named plot theme."""
    _THEMES[name] = theme


def get_theme(name: str) -> PlotTheme:
    """Get a registered plot theme by name."""
    try:
        return _THEMES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown theme '{name}'. Known: {sorted(_THEMES)}") from exc


def list_themes() -> list[str]:
    """List registered theme names."""
    return sorted(_THEMES.keys())


def bootstrap() -> None:
    """Register built-in plot themes.

    External extension machinery has been removed; only built-in themes
    are available.
    """
    register_theme("default", DEFAULT_THEME)
    register_theme("deltares_light", DELTARES_LIGHT)


bootstrap()
