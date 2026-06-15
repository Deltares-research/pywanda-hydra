"""Layout definitions for post-processing plots."""

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
    logo_path = resources.files("pywandahydra.postprocessing.plotting.image_data").joinpath(
        "Deltares_logo.png"
    )
    return plt.imread(str(logo_path))


def load_default_logo() -> Any:
    """Return the default Deltares logo image array."""
    return _default_logo()


# Layout constants
_XO = 0.04
_YO = 0.03
_TEXTBOX_HEIGHT = 0.75


class PageMetadata(BaseModel):
    """Metadata for a plot page layout."""

    model_config = ConfigDict(extra="forbid")

    # Metadata fields
    title: str
    case_title: str
    case_description: str
    proj_number: str
    section_name: str
    fig_name: str

    # Default metadata values
    company_name: str = "Deltares"
    software_version: str = "WANDA 4.8"
    date: datetime | None = None
    company_image: object | None = None  # numpy array or similar

    # Rendering options
    fontsize: int = 8
    font_family: str = "Arial"  # Deltares house style
    watermark_alpha: float = 0.30

    @computed_field
    def effective_date(self) -> datetime:
        return self.date if self.date is not None else datetime.today()

    @field_validator(
        "title",
        "case_title",
        "fig_name",
        "company_name",
        "software_version",
    )
    @classmethod
    def non_empty_str(cls, v: str) -> str:
        """Ensure the string is non-empty after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("proj_number", mode="before")
    @classmethod
    def coerce_project_number(cls, v: Any) -> str | int:
        """Coerce project number to str or int."""
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return str(v)


def _calculate_layout_coordinates() -> tuple[
    tuple[float, float, float, float], tuple[float, float, float, float]
]:
    """Calculate vertical and horizontal layout coordinates.

    Returns
    -------
    tuple[tuple[float, float, float, float], tuple[float, float, float, float]]
        A tuple of (vertical_coords, horizontal_coords) where each is (v0/h0, v1/h1, v2/h2, v3/h3).
    """
    v0 = 0.0 + _XO
    v1 = 0.62 + _XO
    v2 = 0.81
    v3 = 1.0 - _XO

    h0 = 0.0 + _YO
    h1 = 1.2 * _TEXTBOX_HEIGHT / 29.7 + _YO
    h2 = 2.4 * _TEXTBOX_HEIGHT / 29.7 + _YO
    h3 = 3.6 * _TEXTBOX_HEIGHT / 29.7 + _YO

    return (v0, v1, v2, v3), (h0, h1, h2, h3)


def draw_layout(fig: Figure, meta: PageMetadata) -> None:
    """Draw the layout on a matplotlib figure.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to draw the layout on.
    meta : PageMetadata
        The metadata for the page.
    """
    # Import image
    img = meta.company_image or _default_logo()

    # Calculate layout coordinates
    (v0, v1, v2, v3), (h0, h1, h2, h3) = _calculate_layout_coordinates()

    # Draw layout lines (boxes and dividers). matplotlib stubs require a
    # tuple for the rect, but a list is accepted at runtime.
    ax = plt.axes([0, 0, 1, 1], facecolor=(1, 1, 1, 0))  # type: ignore[arg-type]
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    ax.axhline(y=h3, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    ax.axvline(x=v1, ymin=h0, ymax=h3, linewidth=1.5, color="k")
    ax.axhline(y=h1, xmin=v0, xmax=v3, linewidth=1.5, color="k")
    ax.axvline(x=v2, ymin=h0, ymax=h1, linewidth=1.5, color="k")
    ax.axvline(x=v2, ymin=h2, ymax=h3, linewidth=1.5, color="k")
    ax.axhline(y=h2, xmin=v1, xmax=v3, linewidth=1.5, color="k")

    rect = Rectangle((_XO, _YO), 1 - (2 * _XO), 1 - (2 * _YO), fill=False, linewidth=1.5)
    ax.add_patch(rect)

    # Text blocks
    text1 = "\n".join((meta.case_title, meta.case_description))
    fig.text(
        v0 + 0.01,
        (h3 - (h3 - h1) / 2.0),
        text1,
        va="center",
        ha="left",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    fig.text(
        (v1 + (v2 - v1) / 2.0),
        h2 + (h3 - h2) / 2.0,
        meta.section_name,
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    fig.text(
        (v1 + (v2 - v1) / 2.0),
        (h0 + (h1 - h0) / 2.0),
        str(meta.proj_number),
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    fig.text(
        (v0 + (v1 - v0) / 2.0),
        (h0 + (h1 - h0) / 2.0),
        meta.company_name,
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    # Date, figure name, software version
    fig.text(
        (v2 + (v3 - v2) / 2.0),
        h2 + (h3 - h2) / 2.0,
        cast(datetime, meta.effective_date).strftime("%d-%m-%Y"),
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    fig.text(
        (v2 + (v3 - v2) / 2.0),
        (h0 + (h1 - h0) / 2.0),
        meta.fig_name,
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    fig.text(
        (v1 + (v3 - v1) / 2.0),
        h1 + (h2 - h1) / 2.0,
        meta.software_version,
        va="center",
        ha="center",
        color="black",
        fontsize=meta.fontsize,
        fontfamily=meta.font_family,
    )

    # Watermark image (logo)
    imgax = fig.add_axes((v1, h0, v3 - v1, h3 - h0), zorder=-10)
    imgax.imshow(cast(Any, img), alpha=meta.watermark_alpha, interpolation="none")
    imgax.axis("off")
