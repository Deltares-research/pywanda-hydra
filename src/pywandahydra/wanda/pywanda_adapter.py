"""Real WandaAdapter implementation wrapping the pywanda library."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, cast

import numpy as np
import pywanda

from ..config.models import ModelSpecification
from ..scenarios.schema import ParameterChange
from .api import apply_parameter_change, get_item, resolve_items, resolve_route_pipes, to_si_units
from .create_scenario import prepare_scenario_model
from .session import wanda_session

logger = logging.getLogger(__name__)


class PywandaAdapter:
    """Concrete adapter using the pywanda COM/native API.

    Implements the :class:`WandaAdapter` protocol.
    """

    def session(
        self,
        spec: ModelSpecification,
        model_path: Path,
    ) -> AbstractContextManager[pywanda.WandaModel]:
        """Open a WANDA model session context manager."""
        return wanda_session(spec, model_path=model_path)

    def prepare_scenario_model(
        self,
        base_model_path: Path,
        scenario_dir: Path,
        scenario_name: str,
        *,
        readonly: bool,
    ) -> Path:
        """Prepare scenario-specific model files and return model path."""
        return prepare_scenario_model(
            base_model_path,
            scenario_dir,
            scenario_name,
            readonly=readonly,
        )

    def apply(self, handle: pywanda.WandaModel, change: ParameterChange) -> None:
        """Apply a parameter change."""
        apply_parameter_change(handle, change)

    def save_input(self, handle: pywanda.WandaModel) -> None:
        """Save model input before running."""
        handle.save_model_input()

    def simulation_time(self, handle: pywanda.WandaModel) -> float:
        """Get simulation time from model properties."""
        return float(handle.get_property("Simulation time").get_scalar_float())

    @staticmethod
    def _get_item_by_name(handle: pywanda.WandaModel, item_name: str) -> Any:
        """Resolve an item by exact name if possible, else first match."""
        item_refs = resolve_items(handle, item_name)
        if not item_refs:
            raise ValueError(f"Item '{item_name}' not found in model")

        for ref in item_refs:
            if ref.name == item_name:
                return get_item(handle, ref)
        return get_item(handle, item_refs[0])

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
        return float(handle.get_property("Simulation time").get_scalar_float())

    def get_time_steps(self, handle: pywanda.WandaModel) -> list[float]:
        """Get time steps vector from the simulated model.

        Args:
            handle: The WandaModel instance.

        Returns:
            List of time step values.
        """
        return list(handle.get_time_steps())

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
        try:
            handle.read_prop_output(prop)
        except Exception:
            logger.debug(
                "read_prop_output failed for %s.%s",
                component,
                property_name,
                exc_info=True,
            )
        return cast(np.ndarray, to_si_units(np.array(prop.get_series(), dtype=np.float64), prop))

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
        return float(to_si_units(prop.get_scalar_float(), prop))

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

    def resolve_route_pipes(
        self,
        handle: pywanda.WandaModel,
        route_id: str,
    ) -> list[tuple[str, int]]:
        """Resolve route identifier into ordered pipe/direction pairs.

        Args:
            handle: The WandaModel instance.
            route_id: Route identifier.

        Returns:
            List of ``(pipe_name, direction)`` tuples.
        """
        return resolve_route_pipes(handle, route_id)

    def resolve_output_items(
        self,
        handle: pywanda.WandaModel,
        identifier: str,
    ) -> list[str]:
        """Resolve output identifier to concrete model item names."""
        return [ref.name for ref in resolve_items(handle, identifier)]

    def is_pipe_item(self, handle: pywanda.WandaModel, item_name: str) -> bool:
        """Return whether an item is a pipe component."""
        item = self._get_item_by_name(handle, item_name)
        return hasattr(item, "is_pipe") and item.is_pipe()

    def get_pipe_series(
        self,
        handle: pywanda.WandaModel,
        pipe_name: str,
        property_name: str,
    ) -> np.ndarray:
        """Get unit-converted pipe property series."""
        item = self._get_item_by_name(handle, pipe_name)
        if not (hasattr(item, "is_pipe") and item.is_pipe()):
            raise ValueError(f"Item '{pipe_name}' is not a pipe")

        prop = item.get_property(property_name)
        try:
            handle.read_prop_output(prop)
        except Exception:
            logger.debug(
                "read_prop_output failed for pipe %s.%s",
                pipe_name,
                property_name,
                exc_info=True,
            )
        return cast(
            np.ndarray,
            to_si_units(np.asarray(prop.get_series_pipe(), dtype=np.float64), prop),
        )

    def get_pipe_length(self, handle: pywanda.WandaModel, pipe_name: str) -> float:
        """Get pipe length for the named pipe."""
        item = self._get_item_by_name(handle, pipe_name)
        if not (hasattr(item, "is_pipe") and item.is_pipe()):
            raise ValueError(f"Item '{pipe_name}' is not a pipe")
        return float(item.get_property("Length").get_scalar_float())

    def get_pipe_extrema(
        self,
        handle: pywanda.WandaModel,
        pipe_name: str,
        property_name: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get unit-converted min/max arrays for a pipe property."""
        item = self._get_item_by_name(handle, pipe_name)
        if not (hasattr(item, "is_pipe") and item.is_pipe()):
            raise ValueError(f"Item '{pipe_name}' is not a pipe")

        prop = item.get_property(property_name)
        try:
            handle.read_prop_output(prop)
        except Exception:
            logger.debug(
                "read_prop_output failed for pipe %s.%s",
                pipe_name,
                property_name,
                exc_info=True,
            )
        min_vals = to_si_units(np.asarray(prop.get_extr_min_pipe(), dtype=np.float64), prop)
        max_vals = to_si_units(np.asarray(prop.get_extr_max_pipe(), dtype=np.float64), prop)
        return min_vals, max_vals

    def get_pipe_profile_table(
        self,
        handle: pywanda.WandaModel,
        pipe_name: str,
    ) -> np.ndarray:
        """Get raw profile table float data for a pipe."""
        item = self._get_item_by_name(handle, pipe_name)
        if not (hasattr(item, "is_pipe") and item.is_pipe()):
            raise ValueError(f"Item '{pipe_name}' is not a pipe")
        return np.asarray(
            item.get_property("Profile").get_table().get_float_data(),
            dtype=np.float64,
        )
