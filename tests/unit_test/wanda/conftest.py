"""Shared pytest fixtures for wanda tests."""

from __future__ import annotations

# Import shared helper from root conftest
import sys
from pathlib import Path

import pytest

from pywandahydra.config.models import ModelSpecification

sys.path.insert(0, str(Path(__file__).parents[2]))
from conftest import find_wanda_bin


@pytest.fixture(scope="session")
def wanda_model_spec() -> ModelSpecification:
    try:
        wanda_bin = find_wanda_bin()
    except FileNotFoundError as exc:
        pytest.skip(f"WANDA not available: {exc}")
    base_dir = Path(__file__).parents[2] / "data" / "wanda"
    return ModelSpecification(
        model_path=base_dir / "base_model.wdi",
        wanda_bin=wanda_bin,
        base_model_name="base_model",
        run_steady=False,
        run_unsteady=False,
        reuse_existing_data=False,
    )
