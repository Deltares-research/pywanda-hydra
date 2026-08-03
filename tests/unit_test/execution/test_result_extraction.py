from __future__ import annotations

import numpy as np

from pywandahydra.execution.result_extraction import extract_simulation_data
from pywandahydra.results import (
    ComponentIdentity,
    DataRequirements,
    RouteIdentity,
    RouteProductIdentity,
)


class _Access:
    def get_time_steps(self, model: object) -> list[float]:
        return [0.0, 1.0]

    def resolve_output_items(self, model: object, identifier: str) -> list[str]:
        return [identifier]

    def is_pipe_item(self, model: object, item_name: str) -> bool:
        return False

    def get_series(self, model: object, component: str, property_name: str) -> np.ndarray:
        return np.array([1.0, 2.0])

    def resolve_route_pipes(self, model: object, route_id: str) -> list[tuple[str, int]]:
        return [("Pipe A", 1)]

    def get_pipe_length(self, model: object, pipe_name: str) -> float:
        return 10.0

    def get_pipe_series(self, model: object, pipe_name: str, property_name: str) -> np.ndarray:
        return np.array([[1.0, 2.0], [3.0, 4.0]])

    def get_pipe_extrema(
        self, model: object, pipe_name: str, property_name: str
    ) -> tuple[np.ndarray, np.ndarray]:
        return np.array([1.0, 2.0]), np.array([3.0, 4.0])

    def get_pipe_profile_table(self, model: object, pipe_name: str) -> np.ndarray:
        return np.array([[0.0, 0.0], [100.0, 110.0], [0.0, 10.0]])


def test_extracts_typed_data_using_stable_route_identity() -> None:
    route = RouteIdentity("Route A", "Pressure")
    requirements = DataRequirements(
        components=frozenset({ComponentIdentity("Pump A", "Head")} ),
        route_products=frozenset(
            RouteProductIdentity(route, product)
            for product in ("timeseries", "envelope", "profile")
        ),
    )

    data = extract_simulation_data(object(), _Access(), requirements)  # type: ignore[arg-type]

    assert list(data.components.data.iloc[:, 0]) == [1.0, 2.0]
    assert route in data.routes
    assert data.routes[route].envelope is not None
