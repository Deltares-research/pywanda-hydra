from __future__ import annotations

import pandas as pd

from pywandahydra.results import (
    ComponentIdentity,
    ComponentTimeSeries,
    DataRequirements,
    ExtractedSimulationData,
    ResultInventory,
    RouteData,
    RouteIdentity,
    RouteProductIdentity,
)


def test_inventory_reports_missing_component_and_route_products() -> None:
    route = RouteIdentity("route-001", "Pressure")
    data = ExtractedSimulationData(
        components=ComponentTimeSeries(
            pd.DataFrame(
                [[1.0]],
                columns=pd.MultiIndex.from_tuples(
                    [("Pump A", "Head", float("nan"))],
                    names=["component", "property", "s_location"],
                ),
            )
        ),
        routes={route: RouteData(envelope=pd.DataFrame({"min": [1.0]}))},
    )
    inventory = ResultInventory.from_data(data)
    requirements = DataRequirements(
        components=frozenset(
            {
                ComponentIdentity("Pump A", "Head"),
                ComponentIdentity("Pipe A", "Pressure", 10.0),
            }
        ),
        route_products=frozenset(
            {
                RouteProductIdentity(route, "envelope"),
                RouteProductIdentity(route, "profile"),
            }
        ),
    )

    missing = requirements.missing_from(inventory)

    assert missing.components == frozenset({ComponentIdentity("Pipe A", "Pressure", 10.0)})
    assert missing.route_products == frozenset({RouteProductIdentity(route, "profile")})
    assert not inventory.satisfies(requirements)


def test_inventory_uses_route_identity_not_display_name() -> None:
    route = RouteIdentity("route-001", "Pressure")
    inventory = ResultInventory.from_data(
        ExtractedSimulationData(
            routes={route: RouteData(profile=pd.DataFrame({"elevation": [1.0]}))}
        )
    )

    assert inventory.route_products == frozenset({RouteProductIdentity(route, "profile")})
