"""Layout definitions for branded post-processing figures."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from importlib import resources
from typing import Any, cast

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from pydantic import BaseModel, ConfigDict, computed_field, field_validator


@lru_cache(maxsize=1)
def _default_logo() -> Any:
    """Load the default Deltares logo as a numpy array."""
    logo_path = resources.files("pywandahydra.postprocessing.figures.assets").joinpath(
        "Deltares_logo.png"
    )
    return plt.imread(str(logo_path))


def load_default_logo() -> Any:
    """Return the default Deltares logo image array."""
    return _default_logo()


_XO = 0.04
_YO = 0.03
_TEXTBOX_HEIGHT = 0.75


class PageMetadata(BaseModel):
    """Metadata for a plot page layout."""

    model_config = ConfigDict(extra="forbid")
    title: str
    case_title: str
    case_description: str
    proj_number: str
    section_name: str
    fig_name: str
    company_name: str = "Deltares"
    software_version: str = "WANDA 4.8"
    date: datetime | None = None
    company_image: object | None = None
    fontsize: int = 8
    font_family: str = "Arial"
    watermark_alpha: float = 0.30

    @computed_field
    def effective_date(self) -> datetime:
        return self.date if self.date is not None else datetime.today()

    @field_validator("title", "case_title", "fig_name", "company_name", "software_version")
    @classmethod
    def non_empty_str(cls, value: str) -> str:
        """Ensure the string is non-empty after stripping whitespace."""
        value = value.strip()
        if not value:
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("proj_number", mode="before")
    @classmethod
    def coerce_project_number(cls, value: Any) -> str | int:
        """Coerce project number to str or int."""
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return str(value)


def _calculate_layout_coordinates() -> tuple[
    tuple[float, float, float, float], tuple[float, float, float, float]
]:
    """Calculate vertical and horizontal layout coordinates."""
    vertical = (_XO, 0.62 + _XO, 0.81, 1.0 - _XO)
    horizontal = (
        _YO,
        1.2 * _TEXTBOX_HEIGHT / 29.7 + _YO,
        2.4 * _TEXTBOX_HEIGHT / 29.7 + _YO,
        3.6 * _TEXTBOX_HEIGHT / 29.7 + _YO,
    )
    return vertical, horizontal


def draw_layout(figure: Figure, meta: PageMetadata) -> None:
    """Draw the standard Deltares report frame, metadata, and watermark."""
    image = meta.company_image or _default_logo()
    (v0, v1, v2, v3), (h0, h1, h2, h3) = _calculate_layout_coordinates()
    axes = plt.axes([0, 0, 1, 1], facecolor=(1, 1, 1, 0))  # type: ignore[arg-type]
    axes.get_xaxis().set_visible(False)
    axes.get_yaxis().set_visible(False)
    axes.axhline(y=h3, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    axes.axvline(x=v1, ymin=h0, ymax=h3, linewidth=1.5, color="k")
    axes.axhline(y=h1, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    axes.axvline(x=v2, ymin=h0, ymax=h1, linewidth=1.5, color="k")
    axes.axvline(x=v2, ymin=h2, ymax=h3, linewidth=1.5, color="k")
    axes.axhline(y=h2, xmin=v1, xmax=v3, linewidth=1.5, color="k")
    axes.add_patch(Rectangle((_XO, _YO), 1 - (2 * _XO), 1 - (2 * _YO), fill=False, linewidth=1.5))

    text_props: dict[str, Any] = {
        "va": "center",
        "ha": "center",
        "color": "black",
        "fontsize": meta.fontsize,
        "fontfamily": meta.font_family,
    }
    figure.text(
        v0 + 0.01,
        h3 - (h3 - h1) / 2.0,
        "\n".join((meta.case_title, meta.case_description)),
        ha="left",
        va="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )
    figure.text(v1 + (v2 - v1) / 2.0, h2 + (h3 - h2) / 2.0, meta.section_name, **text_props)
    figure.text(v1 + (v2 - v1) / 2.0, h0 + (h1 - h0) / 2.0, str(meta.proj_number), **text_props)
    figure.text(v0 + (v1 - v0) / 2.0, h0 + (h1 - h0) / 2.0, meta.company_name, **text_props)
    figure.text(
        v2 + (v3 - v2) / 2.0,
        h2 + (h3 - h2) / 2.0,
        cast(datetime, meta.effective_date).strftime("%d-%m-%Y"),
        **text_props,
    )
    figure.text(v2 + (v3 - v2) / 2.0, h0 + (h1 - h0) / 2.0, meta.fig_name, **text_props)
    figure.text(v1 + (v3 - v1) / 2.0, h1 + (h2 - h1) / 2.0, meta.software_version, **text_props)
    image_axes = figure.add_axes((v1, h0, v3 - v1, h3 - h0), zorder=-10)
    image_axes.imshow(cast(Any, image), alpha=meta.watermark_alpha, interpolation="none")
    image_axes.axis("off")
