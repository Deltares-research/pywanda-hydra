"""Static WANDA model-access protocol."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, TypeAlias

import numpy as np

from ..config.models import ModelSpecification
from ..scenarios.schema import ParameterChange

ModelHandle: TypeAlias = Any


class WandaModelAccess(Protocol):
    """Protocol abstracting all pywanda interactions used by production code."""

    def session(
        self,
        spec: ModelSpecification,
        model_path: Path,
    ) -> AbstractContextManager[ModelHandle]:
        ...

    def prepare_scenario_model(
        self,
        base_model_path: Path,
        scenario_dir: Path,
        scenario_name: str,
        *,
        reuse_existing_data: bool,
    ) -> Path:
        ...

    def apply(self, handle: Any, change: ParameterChange) -> None:
        ...

    def save_input(self, handle: Any) -> None:
        ...

    def run_steady(self, handle: Any) -> None:
        ...

    def run_unsteady(self, handle: Any) -> None:
        ...

    def simulation_time(self, handle: Any) -> float:
        ...

    def get_time_steps(self, handle: Any) -> list[float]:
        ...

    def get_series(self, handle: Any, component: str, property_name: str) -> np.ndarray:
        ...

    def get_scalar(self, handle: Any, component: str, property_name: str) -> float:
        ...

    def resolve_route_components(self, handle: Any, route_id: str) -> list[str]:
        ...

    def resolve_route_pipes(self, handle: Any, route_id: str) -> list[tuple[str, int]]:
        ...

    def resolve_output_items(self, handle: Any, identifier: str) -> list[str]:
        ...

    def is_pipe_item(self, handle: Any, item_name: str) -> bool:
        ...

    def get_pipe_series(
        self,
        handle: Any,
        pipe_name: str,
        property_name: str,
    ) -> np.ndarray:
        ...

    def get_pipe_length(self, handle: Any, pipe_name: str) -> float:
        ...

    def get_pipe_extrema(
        self,
        handle: Any,
        pipe_name: str,
        property_name: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        ...

    def get_pipe_profile_table(self, handle: Any, pipe_name: str) -> np.ndarray:
        ...
