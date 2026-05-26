"""Fake WandaAdapter for testing — no real WANDA installation required."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..scenarios.schema import ParameterChange


class FakeAdapter:
    """In-memory test double implementing the WandaAdapter protocol.

    Records all calls and returns configurable fake data. Useful for
    unit-testing the runner, worker, and extraction pipeline without
    needing a real WANDA model.

    Attributes:
        calls: List of (method_name, args) tuples recording all interactions.
        series_data: Configurable dict mapping (component, property) → ndarray.
        scalar_data: Configurable dict mapping (component, property) → float.
        route_components: Configurable dict mapping route_id → list of component names.
        time_steps: Configurable time step vector.
        simulation_time: Configurable simulation time value.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.series_data: dict[tuple[str, str], np.ndarray] = {}
        self.scalar_data: dict[tuple[str, str], float] = {}
        self.route_components: dict[str, list[str]] = {}
        self.time_steps: list[float] = [float(i) for i in range(100)]
        self.simulation_time: float = 100.0
        self._open_count: int = 0
        self._close_count: int = 0

    @property
    def open_count(self) -> int:
        """Number of times open() was called."""
        return self._open_count

    @property
    def close_count(self) -> int:
        """Number of times close() was called."""
        return self._close_count

    def open(self, model_path: str, wanda_bin: str) -> str:
        """Fake open — returns model_path as the handle.

        Args:
            model_path: Path to the model file.
            wanda_bin: Path to WANDA binaries.

        Returns:
            The model_path string as a fake handle.
        """
        self.calls.append(("open", (model_path, wanda_bin)))
        self._open_count += 1
        return model_path

    def close(self, handle: Any) -> None:
        """Fake close.

        Args:
            handle: The fake model handle.
        """
        self.calls.append(("close", (handle,)))
        self._close_count += 1

    def save_model_input(self, handle: Any) -> None:
        """Fake save_model_input.

        Args:
            handle: The fake model handle.
        """
        self.calls.append(("save_model_input", (handle,)))

    def apply_parameter_change(self, handle: Any, change: ParameterChange) -> None:
        """Fake apply — records the change.

        Args:
            handle: The fake model handle.
            change: The parameter change.
        """
        self.calls.append(("apply_parameter_change", (handle, change)))

    def run_steady(self, handle: Any) -> None:
        """Fake run_steady.

        Args:
            handle: The fake model handle.
        """
        self.calls.append(("run_steady", (handle,)))

    def run_unsteady(self, handle: Any) -> None:
        """Fake run_unsteady.

        Args:
            handle: The fake model handle.
        """
        self.calls.append(("run_unsteady", (handle,)))

    def get_simulation_time(self, handle: Any) -> float:
        """Fake get_simulation_time.

        Args:
            handle: The fake model handle.

        Returns:
            Configured simulation_time value.
        """
        self.calls.append(("get_simulation_time", (handle,)))
        return self.simulation_time

    def get_time_steps(self, handle: Any) -> list[float]:
        """Fake get_time_steps.

        Args:
            handle: The fake model handle.

        Returns:
            Configured time_steps list.
        """
        self.calls.append(("get_time_steps", (handle,)))
        return self.time_steps

    def get_series(
        self, handle: Any, component: str, property_name: str
    ) -> np.ndarray:
        """Fake get_series — returns configured data or zeros.

        Args:
            handle: The fake model handle.
            component: Component name.
            property_name: Property name.

        Returns:
            numpy array (from series_data or zeros).
        """
        self.calls.append(("get_series", (handle, component, property_name)))
        key = (component, property_name)
        if key in self.series_data:
            return self.series_data[key]
        return np.zeros(len(self.time_steps), dtype=np.float64)

    def get_scalar(
        self, handle: Any, component: str, property_name: str
    ) -> float:
        """Fake get_scalar — returns configured data or 0.0.

        Args:
            handle: The fake model handle.
            component: Component name.
            property_name: Property name.

        Returns:
            Float value (from scalar_data or 0.0).
        """
        self.calls.append(("get_scalar", (handle, component, property_name)))
        key = (component, property_name)
        if key in self.scalar_data:
            return self.scalar_data[key]
        return 0.0

    def resolve_route_components(
        self, handle: Any, route_id: str
    ) -> list[str]:
        """Fake resolve_route_components.

        Args:
            handle: The fake model handle.
            route_id: Route identifier.

        Returns:
            Configured component list or empty list.
        """
        self.calls.append(("resolve_route_components", (handle, route_id)))
        return self.route_components.get(route_id, [])
