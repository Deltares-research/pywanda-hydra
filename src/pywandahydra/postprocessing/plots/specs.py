"""Plot specification hierarchy — declarative definitions for plots and tables."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..plotting.specifications import AxisSpec


# ---------------------------------------------------------------------------
# Signal request — what data is needed from the model
# ---------------------------------------------------------------------------


class SignalRequest(BaseModel):
    """A single data request to be extracted from the model.

    Attributes:
        component: Component identifier (name or keyword).
        property_name: Property to extract.
        kind: Type of extraction.
    """

    model_config = ConfigDict(frozen=True)

    component: str
    property_name: str
    kind: Literal["series", "scalar"] = "series"


# ---------------------------------------------------------------------------
# PlotSpec base and concrete subclasses
# ---------------------------------------------------------------------------


class PlotSpec(BaseModel):
    """Base class for all plot specifications.

    Subclasses define the specific plot type and its required signals.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique plot identifier")
    title: Optional[str] = None

    def required_signals(self) -> list[SignalRequest]:
        """Return the list of signals this plot needs extracted.

        Returns:
            List of SignalRequest objects.
        """
        raise NotImplementedError


class RoutePlotSpec(PlotSpec):
    """Route plot — property along a spatial route.

    Attributes:
        route_id: Identifier for the route (keyword or name).
        property_name: Property to plot along the route.
        x_axis: X-axis specification.
        y_axis: Y-axis specification.
        legend: Optional legend label.
    """

    route_id: str
    property_name: str
    x_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label="Distance [m]"))
    y_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))
    legend: Optional[str] = None

    def required_signals(self) -> list[SignalRequest]:
        """Route plots need series data for each component on the route."""
        # The actual component list is resolved at extraction time via adapter
        return [SignalRequest(
            component=self.route_id,
            property_name=self.property_name,
            kind="series",
        )]


class TimeSeriesPlotSpec(PlotSpec):
    """Time-series plot — property over time for one or more components.

    Attributes:
        components: List of component identifiers to plot.
        property_name: Property to plot over time.
        x_axis: X-axis specification.
        y_axis: Y-axis specification.
    """

    components: list[str]
    property_name: str
    x_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label="Time [s]"))
    y_axis: AxisSpec = Field(default_factory=lambda: AxisSpec(label=""))

    def required_signals(self) -> list[SignalRequest]:
        """Time series plots need series data for each listed component."""
        return [
            SignalRequest(
                component=comp,
                property_name=self.property_name,
                kind="series",
            )
            for comp in self.components
        ]


class ScalarTableSpec(PlotSpec):
    """Scalar table — min/max/mean of a property across components.

    Attributes:
        component: Component identifier.
        property_name: Property to aggregate.
        reduce: Reduction mode.
    """

    component: str
    property_name: str
    reduce: Literal["MIN", "MAX", "MEAN"] = "MAX"

    def required_signals(self) -> list[SignalRequest]:
        """Scalar tables need series data to compute aggregates."""
        return [SignalRequest(
            component=self.component,
            property_name=self.property_name,
            kind="series",
        )]
