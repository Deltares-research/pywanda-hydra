"""WANDA-free scientific result contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

import pandas as pd

RouteProduct = Literal["timeseries", "envelope", "profile"]


@dataclass(frozen=True, order=True, slots=True)
class ComponentIdentity:
    """Stable identity for one component output column."""

    component: str
    property: str
    location: float | None = None


@dataclass(frozen=True, order=True, slots=True)
class RouteIdentity:
    """Stable route/property identity independent of display metadata."""

    route_id: str
    property: str


@dataclass(frozen=True, order=True, slots=True)
class RouteProductIdentity:
    """Stable identity for one product generated for a route property."""

    route: RouteIdentity
    product: RouteProduct


@dataclass(frozen=True, slots=True)
class ComponentTimeSeries:
    """Component output time series with owned DataFrame payload."""

    data: pd.DataFrame

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", self.data.copy(deep=True))


@dataclass(frozen=True, slots=True)
class RouteData:
    """Owned route products for one stable route/property identity."""

    timeseries: pd.DataFrame | None = None
    envelope: pd.DataFrame | None = None
    profile: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        for product in ("timeseries", "envelope", "profile"):
            value = getattr(self, product)
            if value is not None:
                object.__setattr__(self, product, value.copy(deep=True))

    def products(self) -> tuple[RouteProduct, ...]:
        """Return products present in this payload."""
        return tuple(
            cast(RouteProduct, product)
            for product in ("timeseries", "envelope", "profile")
            if getattr(self, product) is not None
        )


@dataclass(frozen=True, slots=True)
class ExtractedSimulationData:
    """All WANDA-free data extracted for one simulated case."""

    components: ComponentTimeSeries = field(
        default_factory=lambda: ComponentTimeSeries(pd.DataFrame())
    )
    routes: Mapping[RouteIdentity, RouteData] = field(default_factory=dict)

    def __post_init__(self) -> None:
        copied_routes = {identity: data for identity, data in self.routes.items()}
        object.__setattr__(self, "routes", MappingProxyType(copied_routes))


def component_identities(data: ComponentTimeSeries) -> frozenset[ComponentIdentity]:
    """Derive stable component identities from three-level component columns."""
    if not isinstance(data.data.columns, pd.MultiIndex) or data.data.columns.nlevels != 3:
        return frozenset()
    identities: set[ComponentIdentity] = set()
    for component, property_name, location in data.data.columns:
        numeric_location = None if pd.isna(location) else float(location)
        identities.add(ComponentIdentity(str(component), str(property_name), numeric_location))
    return frozenset(identities)
