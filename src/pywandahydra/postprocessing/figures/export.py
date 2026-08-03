"""Figure output utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

DEFAULT_FIGURE_EXPORT_PROPS: dict[str, dict[str, Any]] = {".pdf": {}}
OPTIONAL_FIGURE_EXPORT_PROPS: dict[str, dict[str, Any]] = {
    ".png": {"transparent": False, "dpi": 300},
    ".svg": {"transparent": True},
}


def build_figure_export_props(
    *, include_pdf: bool = True, include_png: bool = False, include_svg: bool = False
) -> dict[str, dict[str, Any]]:
    """Build configured figure export formats."""
    props: dict[str, dict[str, Any]] = {}
    if include_pdf:
        props.update(DEFAULT_FIGURE_EXPORT_PROPS)
    if include_png:
        props[".png"] = OPTIONAL_FIGURE_EXPORT_PROPS[".png"]
    if include_svg:
        props[".svg"] = OPTIONAL_FIGURE_EXPORT_PROPS[".svg"]
    return props


def savefig(
    figure: Figure,
    output_dir: Path,
    filename: str,
    *,
    export_props: dict[str, dict[str, Any]] | None = None,
    close: bool = True,
) -> list[Path]:
    """Save a figure in one or more configured formats."""
    saved: list[Path] = []
    for extension, options in (export_props or DEFAULT_FIGURE_EXPORT_PROPS).items():
        directory = output_dir if extension == ".pdf" else output_dir / f"{extension[1:]}-files"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{filename}{extension}"
        figure.savefig(path, bbox_inches="tight", **options)
        saved.append(path)
    if close:
        import matplotlib.pyplot as plt

        plt.close(figure)
    return saved