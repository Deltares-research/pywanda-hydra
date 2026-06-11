"""Theme registry and entry-point discovery for plotting themes."""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from .renderer import PlotTheme

logger = logging.getLogger(__name__)

DEFAULT_THEME = PlotTheme()
DELTARES_LIGHT = PlotTheme()

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
    """Register built-in themes and load theme entry-point plugins."""
    register_theme("default", DEFAULT_THEME)
    register_theme("deltares_light", DELTARES_LIGHT)

    for ep in entry_points(group="pywandahydra.themes"):
        try:
            loaded = ep.load()
            if isinstance(loaded, PlotTheme):
                register_theme(ep.name, loaded)
            elif callable(loaded):
                produced = loaded()
                if isinstance(produced, PlotTheme):
                    register_theme(ep.name, produced)
                else:
                    raise TypeError("Callable theme plugin must return PlotTheme")
            else:
                raise TypeError("Theme plugin must be PlotTheme or callable returning PlotTheme")
        except Exception:
            logger.exception("Failed to load pywandahydra.themes plugin %r", ep.name)


bootstrap()
