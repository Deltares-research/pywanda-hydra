"""WandaAdapter protocol — abstracts all pywanda interactions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np

from ..scenarios.schema import ParameterChange


@runtime_checkable
class WandaAdapter(Protocol):
    """Protocol abstracting the pywanda model API.

    All pywanda interactions must go through an adapter so that the
    execution layer can be tested without a real WANDA installation.
    """

    def open(self, model_path: str, wanda_bin: str) -> Any:
        """Open a WANDA model and return an opaque handle.

        Args:
            model_path: Path to the .wdi model file.
            wanda_bin: Path to the WANDA binaries directory.

        Returns:
            An opaque model handle used by other adapter methods.
        """
        ...

    def close(self, handle: Any) -> None:
        """Close a previously opened WANDA model.

        Args:
            handle: The model handle returned by ``open``.
        """
        ...

    def save_model_input(self, handle: Any) -> None:
        """Save model input before running.

        Args:
            handle: The model handle.
        """
        ...

    def apply_parameter_change(self, handle: Any, change: ParameterChange) -> None:
        """Apply a single parameter change to the open model.

        Args:
            handle: The model handle.
            change: The parameter change to apply.
        """
        ...

    def run_steady(self, handle: Any) -> None:
        """Run steady-state simulation.

        Args:
            handle: The model handle.
        """
        ...

    def run_unsteady(self, handle: Any) -> None:
        """Run unsteady (transient) simulation.

        Args:
            handle: The model handle.
        """
        ...

    def get_simulation_time(self, handle: Any) -> float:
        """Get the simulation time from model properties.

        Args:
            handle: The model handle.

        Returns:
            Simulation time in seconds.
        """
        ...

    def get_time_steps(self, handle: Any) -> list[float]:
        """Get the time steps vector from the simulated model.

        Args:
            handle: The model handle.

        Returns:
            List of time step values.
        """
        ...

    def get_series(
        self, handle: Any, component: str, property_name: str
    ) -> np.ndarray:
        """Get a time-series array for a component property.

        Args:
            handle: The model handle.
            component: Component identifier (exact name or keyword).
            property_name: Property name to extract.

        Returns:
            1-D numpy array of the time series.
        """
        ...

    def get_scalar(
        self, handle: Any, component: str, property_name: str
    ) -> float:
        """Get a scalar value for a component property.

        Args:
            handle: The model handle.
            component: Component identifier.
            property_name: Property name.

        Returns:
            Scalar float value.
        """
        ...

    def resolve_route_components(
        self, handle: Any, route_id: str
    ) -> list[str]:
        """Resolve a route identifier into ordered component names.

        Args:
            handle: The model handle.
            route_id: Route identifier (e.g. keyword or exact name).

        Returns:
            Ordered list of component names along the route.
        """
        ...
