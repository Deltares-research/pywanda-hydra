"""Explicit raw-data requirements and available-result inventory."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    ComponentIdentity,
    ExtractedSimulationData,
    RouteProductIdentity,
    component_identities,
)


@dataclass(frozen=True, slots=True)
class DataRequirements:
    """Raw result identities required by a downstream operation."""

    components: frozenset[ComponentIdentity] = field(default_factory=frozenset)
    route_products: frozenset[RouteProductIdentity] = field(default_factory=frozenset)

    def missing_from(self, inventory: ResultInventory) -> DataRequirements:
        """Return the portion of this requirement not present in ``inventory``."""
        return DataRequirements(
            components=self.components - inventory.components,
            route_products=self.route_products - inventory.route_products,
        )

    def is_satisfied_by(self, inventory: ResultInventory) -> bool:
        """Whether ``inventory`` contains all required raw data."""
        return not self.missing_from(inventory).components and not self.missing_from(
            inventory
        ).route_products


@dataclass(frozen=True, slots=True)
class ResultInventory:
    """Stable inventory of raw result identities present in a store."""

    components: frozenset[ComponentIdentity] = field(default_factory=frozenset)
    route_products: frozenset[RouteProductIdentity] = field(default_factory=frozenset)

    @classmethod
    def from_data(cls, data: ExtractedSimulationData) -> ResultInventory:
        """Build an inventory from an extracted simulation payload."""
        route_products = frozenset(
            RouteProductIdentity(route, product)
            for route, route_data in data.routes.items()
            for product in route_data.products()
        )
        return cls(components=component_identities(data.components), route_products=route_products)

    def satisfies(self, requirements: DataRequirements) -> bool:
        """Whether this inventory satisfies ``requirements``."""
        return requirements.is_satisfied_by(self)
