"""Shared pytest fixtures for integration tests."""

from __future__ import annotations

# Import shared helper from root conftest
import sys
from pathlib import Path

import pytest

from pywandahydra.execution.plans import ModelSpecification

sys.path.insert(0, str(Path(__file__).parents[1]))
from conftest import find_wanda_bin

_WANDA_DATA_DIR = Path(__file__).parents[1] / "data" / "wanda"
_INTEGRATION_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def wanda_model_spec() -> ModelSpecification:
    try:
        wanda_bin = find_wanda_bin()
    except FileNotFoundError as exc:
        pytest.skip(f"WANDA not available: {exc}")
    return ModelSpecification(
        model_path=_WANDA_DATA_DIR / "base_model.wdi",
        wanda_bin=wanda_bin,
        run_steady=False,
        run_unsteady=False,
    )


@pytest.fixture(scope="session")
def network_model_spec() -> ModelSpecification:
    try:
        wanda_bin = find_wanda_bin()
    except FileNotFoundError as exc:
        pytest.skip(f"WANDA not available: {exc}")
    return ModelSpecification(
        model_path=_INTEGRATION_DATA_DIR / "network.wdi",
        wanda_bin=wanda_bin,
        run_steady=True,
        run_unsteady=False,
    )
