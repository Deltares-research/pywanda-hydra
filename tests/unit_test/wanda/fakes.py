from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np

from pywandahydra.execution.plans import ModelSpecification
from pywandahydra.scenarios import ModelParameterChange

ModelHandle = Any


class FakeWandaModelAccess:
    """In-memory adapter used by worker tests without pywanda dependency."""

    @contextmanager
    def session(self, spec: ModelSpecification, model_path: Path):
        del spec, model_path
        yield {"fake": True}

    def prepare_scenario_model(
        self,
        base_model_path: Path,
        scenario_dir: Path,
        scenario_name: str,
        *,
        reuse_existing_data: bool,
    ) -> Path:
        scenario_dir.mkdir(parents=True, exist_ok=True)
        target = scenario_dir / f"{base_model_path.stem}_{scenario_name}.wdi"
        if reuse_existing_data and target.exists():
            return target
        target.write_bytes(base_model_path.read_bytes())
        return target

    def apply(self, handle: ModelHandle, change: ModelParameterChange) -> None:
        del handle, change

    def save_input(self, handle: ModelHandle) -> None:
        del handle

    def run_steady(self, handle: ModelHandle) -> None:
        del handle

    def run_unsteady(self, handle: ModelHandle) -> None:
        del handle

    def simulation_time(self, handle: ModelHandle) -> float:
        del handle
        return 0.0

    def get_time_steps(self, handle: ModelHandle) -> list[float]:
        del handle
        return [0.0]

    def get_series(self, handle: ModelHandle, component: str, property_name: str) -> np.ndarray:
        del handle, component, property_name
        return np.array([0.0], dtype=np.float64)

    def get_scalar(self, handle: ModelHandle, component: str, property_name: str) -> float:
        del handle, component, property_name
        return 0.0

    def resolve_route_components(self, handle: ModelHandle, route_id: str) -> list[str]:
        del handle, route_id
        return []

    def resolve_route_pipes(self, handle: ModelHandle, route_id: str) -> list[tuple[str, int]]:
        del handle, route_id
        return []

    def resolve_output_items(self, handle: ModelHandle, identifier: str) -> list[str]:
        del handle, identifier
        return []

    def is_pipe_item(self, handle: ModelHandle, item_name: str) -> bool:
        del handle, item_name
        return False

    def get_pipe_series(
        self,
        handle: ModelHandle,
        pipe_name: str,
        property_name: str,
    ) -> np.ndarray:
        del handle, pipe_name, property_name
        return np.array([[0.0]], dtype=np.float64)

    def get_pipe_length(self, handle: ModelHandle, pipe_name: str) -> float:
        del handle, pipe_name
        return 0.0

    def get_pipe_extrema(
        self,
        handle: ModelHandle,
        pipe_name: str,
        property_name: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        del handle, pipe_name, property_name
        base = np.array([0.0], dtype=np.float64)
        return base, base

    def get_pipe_profile_table(self, handle: ModelHandle, pipe_name: str) -> np.ndarray:
        del handle, pipe_name
        return np.zeros((3, 1), dtype=np.float64)


class FailingWandaModelAccess(FakeWandaModelAccess):
    """Fake adapter whose steady-state run always raises.

    Used to exercise the worker's failure path (journal transition to
    FAILED and the resulting CaseResult) without a real WANDA session.
    """

    def run_steady(self, handle: ModelHandle) -> None:
        del handle
        raise RuntimeError("simulated steady-state failure")


# Backward-compatible aliases for older test names.
FakeWandaAdapter = FakeWandaModelAccess
FailingWandaAdapter = FailingWandaModelAccess
