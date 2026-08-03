"""Internal production WANDA model-access implementation using pywanda."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, cast

import numpy as np
import pywanda

from ..execution.legacy import ModelSpecification
from ..scenarios import ModelParameterChange
from .item_lookup import get_item, resolve_items
from .model_files import prepare_scenario_model
from .parameter_application import apply_parameter_change, to_si_units
from .route_tracing import resolve_route_pipes
from .session import wanda_session

logger = logging.getLogger(__name__)


class PywandaModelAccess:
    """Concrete model-access implementation wrapping pywanda."""

    def session(
        self,
        spec: ModelSpecification,
        model_path: Path,
    ) -> AbstractContextManager[pywanda.WandaModel]:
        return wanda_session(spec, model_path=model_path)

    def prepare_scenario_model(
        self,
        base_model_path: Path,
        scenario_dir: Path,
        scenario_name: str,
        *,
        reuse_existing_data: bool,
    ) -> Path:
        del reuse_existing_data
        return prepare_scenario_model(
            base_model_path,
            scenario_dir,
            scenario_name,
        )

    def apply(self, handle: pywanda.WandaModel, change: ModelParameterChange) -> None:
        apply_parameter_change(handle, change)

    def save_input(self, handle: pywanda.WandaModel) -> None:
        handle.save_model_input()

    def simulation_time(self, handle: pywanda.WandaModel) -> float:
        return float(handle.get_property("Simulation time").get_scalar_float())

    @staticmethod
    def _get_item_by_name(handle: pywanda.WandaModel, item_name: str) -> Any:
        item_refs = resolve_items(handle, item_name)
        if not item_refs:
            raise ValueError(f"Item '{item_name}' not found in model")

        for ref in item_refs:
            if ref.name == item_name:
                return get_item(handle, ref)
        return get_item(handle, item_refs[0])

    def run_steady(self, handle: pywanda.WandaModel) -> None:
        handle.run_steady()

    def run_unsteady(self, handle: pywanda.WandaModel) -> None:
        handle.run_unsteady()

    def get_time_steps(self, handle: pywanda.WandaModel) -> list[float]:
        return list(handle.get_time_steps())

    def get_series(
        self, handle: pywanda.WandaModel, component: str, property_name: str
    ) -> np.ndarray:
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
        item_refs = resolve_items(handle, component)
        if not item_refs:
            raise ValueError(f"Component '{component}' not found in model")
        item = get_item(handle, item_refs[0])
        prop = item.get_property(property_name)
        return float(to_si_units(prop.get_scalar_float(), prop))

    def resolve_route_components(self, handle: pywanda.WandaModel, route_id: str) -> list[str]:
        item_refs = resolve_items(handle, route_id)
        return [ref.name for ref in item_refs]

    def resolve_route_pipes(
        self,
        handle: pywanda.WandaModel,
        route_id: str,
    ) -> list[tuple[str, int]]:
        return resolve_route_pipes(handle, route_id)

    def resolve_output_items(
        self,
        handle: pywanda.WandaModel,
        identifier: str,
    ) -> list[str]:
        return [ref.name for ref in resolve_items(handle, identifier)]

    def is_pipe_item(self, handle: pywanda.WandaModel, item_name: str) -> bool:
        item = self._get_item_by_name(handle, item_name)
        return hasattr(item, "is_pipe") and item.is_pipe()

    def get_pipe_series(
        self,
        handle: pywanda.WandaModel,
        pipe_name: str,
        property_name: str,
    ) -> np.ndarray:
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
        item = self._get_item_by_name(handle, pipe_name)
        if not (hasattr(item, "is_pipe") and item.is_pipe()):
            raise ValueError(f"Item '{pipe_name}' is not a pipe")
        return np.asarray(
            item.get_property("Profile").get_table().get_float_data(),
            dtype=np.float64,
        )
