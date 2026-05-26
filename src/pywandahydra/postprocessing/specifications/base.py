"""General base classes for post-processing specifications."""

from pydantic import BaseModel


class PlotSpecification(BaseModel):
    """Base class for plot specifications in post-processing."""

    name: str
