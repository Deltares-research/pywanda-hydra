"""WandaAdapter protocol — abstracts all pywanda interactions."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, TypeAlias, runtime_checkable

import numpy as np

from ..config.models import ModelSpecification
from ..scenarios.schema import ParameterChange

ModelHandle: TypeAlias = Any


@runtime_checkable
class WandaAdapter(Protocol):
    """Protocol abstracting the pywanda model API.

    All pywanda interactions must go through an adapter so that the
    execution layer can be tested without a real WANDA installation.
    """

    def session(
        self,
        spec: ModelSpecification,
        model_path: Path,
    ) -> AbstractContextManager[ModelHandle]:
        """Open a WANDA model session and return a context manager.

        Args:
            spec: Model specification with run settings and wanda path.
            model_path: Path to the scenario-specific .wdi file.

        Returns:
            Context manager yielding an opaque model handle.
        """
        ...

    def prepare_scenario_model(
        self,
        base_model_path: Path,
        scenario_dir: Path,
        scenario_name: str,
        *,
        reuse_existing_data: bool,
    ) -> Path:
        """Create or reuse a scenario-specific model file.

        Args:
            base_model_path: Path to the base model .wdi.
            scenario_dir: Case output directory.
            scenario_name: Scenario name.
            reuse_existing_data: Whether to reuse existing files.

        Returns:
            Path to the scenario model .wdi file.
        """
        ...

    def apply(self, handle: Any, change: ParameterChange) -> None:
        """Apply a single parameter change to the open model."""
        ...

    def save_input(self, handle: Any) -> None:
        """Save model input before running.

        Args:
            handle: The model handle.
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

    def simulation_time(self, handle: Any) -> float:
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

    def get_series(self, handle: Any, component: str, property_name: str) -> np.ndarray:
        """Get a time-series array for a component property.

        Args:
            handle: The model handle.
            component: Component identifier (exact name or keyword).
            property_name: Property name to extract.

        Returns:
            1-D numpy array of the time series.
        """
        ...

    def get_scalar(self, handle: Any, component: str, property_name: str) -> float:
        """Get a scalar value for a component property.

        Args:
            handle: The model handle.
            component: Component identifier.
            property_name: Property name.

        Returns:
            Scalar float value.
        """
        ...

    def resolve_route_components(self, handle: Any, route_id: str) -> list[str]:
        """Resolve a route identifier into ordered component names.

        Args:
            handle: The model handle.
            route_id: Route identifier (e.g. keyword or exact name).

        Returns:
            Ordered list of component names along the route.
        """
        ...

    def resolve_route_pipes(self, handle: Any, route_id: str) -> list[tuple[str, int]]:
        """Resolve route identifier into ordered pipes with direction.

        Args:
            handle: The model handle.
            route_id: Route identifier (keyword or exact route name).

        Returns:
            List of ``(pipe_name, direction)`` where direction is
            ``+1`` for forward and ``-1`` for reverse traversal.
        """
        ...

    def resolve_output_items(
        self,
        handle: Any,
        identifier: str,
    ) -> list[str]:
        """Resolve output identifier to concrete item names."""
        ...

    def is_pipe_item(self, handle: Any, item_name: str) -> bool:
        """Return whether an item is a pipe component."""
        ...

    def get_pipe_series(
        self,
        handle: Any,
        pipe_name: str,
        property_name: str,
    ) -> np.ndarray:
        """Get unit-converted pipe series for a property."""
        ...

    def get_pipe_length(self, handle: Any, pipe_name: str) -> float:
        """Get pipe length in model units."""
        ...

    def get_pipe_extrema(
        self,
        handle: Any,
        pipe_name: str,
        property_name: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get unit-converted min/max envelopes for a pipe property."""
        ...

    def get_pipe_profile_table(self, handle: Any, pipe_name: str) -> np.ndarray:
        """Get raw pipe profile table float data."""
        ...
