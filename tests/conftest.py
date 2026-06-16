"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture
def make_scenario() -> Callable[..., ScenarioSpecification]:
    def _factory(
        name: str = "case_001", number: int = 1, include: bool = True
    ) -> ScenarioSpecification:
        return ScenarioSpecification(
            meta=ScenarioMeta.model_validate(
                {"Number": number, "Include": include, "Name": name}
            )
        )

    return _factory
