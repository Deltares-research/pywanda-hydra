"""General base classes for post-processing specifications."""

from pydantic import BaseModel


class PlotSpec(BaseModel):
    """Base class for plot specifications in post-processing."""

    name: str
