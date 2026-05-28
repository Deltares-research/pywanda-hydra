"""Real WandaAdapter implementation wrapping the pywanda library."""

from __future__ import annotations

from typing import Any

import numpy as np
import pywanda

from ..scenarios.schema import ParameterChange
from .api import apply_parameter_change, get_item, resolve_items


class PywandaAdapter:
    """Concrete adapter using the pywanda COM/native API.

    Implements the :class:`WandaAdapter` protocol.
    """

    def open(self, model_path: str, wanda_bin: str) -> pywanda.WandaModel:
        """Open a WANDA model via pywanda.

        Args:
            model_path: Path to the .wdi model file.
            wanda_bin: Path to the WANDA binaries directory.

        Returns:
            A pywanda.WandaModel instance.
        """
        return pywanda.WandaModel(model_path, wanda_bin)

    def close(self, handle: pywanda.WandaModel) -> None:
        """Close the WANDA model.

        Args:
            handle: The WandaModel instance.
        """
        handle.close()

    def save_model_input(self, handle: pywanda.WandaModel) -> None:
        """Save model input before running.

        Args:
            handle: The WandaModel instance.
        """
        handle.save_model_input()

    def apply_parameter_change(self, handle: pywanda.WandaModel, change: ParameterChange) -> None:
        """Apply a parameter change using the existing api module.

        Args:
            handle: The WandaModel instance.
            change: The parameter change to apply.
        """
        apply_parameter_change(handle, change)

    def run_steady(self, handle: pywanda.WandaModel) -> None:
        """Run steady-state simulation.

        Args:
            handle: The WandaModel instance.
        """
        handle.run_steady()

    def run_unsteady(self, handle: pywanda.WandaModel) -> None:
        """Run unsteady simulation.

        Args:
            handle: The WandaModel instance.
        """
        handle.run_unsteady()

    def get_simulation_time(self, handle: pywanda.WandaModel) -> float:
        """Get simulation time from model properties.

        Args:
            handle: The WandaModel instance.

        Returns:
            Simulation time in seconds.
        """
        return handle.get_property("Simulation time").get_scalar_float()

    def get_time_steps(self, handle: pywanda.WandaModel) -> list[float]:
        """Get time steps vector from the simulated model.

        Args:
            handle: The WandaModel instance.

        Returns:
            List of time step values.
        """
        return handle.get_time_steps()

    def get_series(
        self, handle: pywanda.WandaModel, component: str, property_name: str
    ) -> np.ndarray:
        """Get time-series for a component property.

        Args:
            handle: The WandaModel instance.
            component: Component identifier.
            property_name: Property name.

        Returns:
            1-D numpy array.
        """
        item_refs = resolve_items(handle, component)
        if not item_refs:
            raise ValueError(f"Component '{component}' not found in model")
        item = get_item(handle, item_refs[0])
        prop = item.get_property(property_name)
        return np.array(prop.get_series(), dtype=np.float64)

    def get_scalar(self, handle: pywanda.WandaModel, component: str, property_name: str) -> float:
        """Get scalar value for a component property.

        Args:
            handle: The WandaModel instance.
            component: Component identifier.
            property_name: Property name.

        Returns:
            Scalar float.
        """
        item_refs = resolve_items(handle, component)
        if not item_refs:
            raise ValueError(f"Component '{component}' not found in model")
        item = get_item(handle, item_refs[0])
        prop = item.get_property(property_name)
        return float(prop.get_scalar_float())

    def resolve_route_components(self, handle: pywanda.WandaModel, route_id: str) -> list[str]:
        """Resolve route identifier into component names.

        Args:
            handle: The WandaModel instance.
            route_id: Route identifier.

        Returns:
            Ordered list of component names.
        """
        item_refs = resolve_items(handle, route_id)
        return [ref.name for ref in item_refs]
