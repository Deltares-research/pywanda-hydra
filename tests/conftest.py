"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from pywandahydra.scenarios import ScenarioSpecification

DATA_DIR = Path(__file__).parent / "data"

_SEARCH_ROOTS = (
    Path(r"C:\Program Files (x86)\Deltares"),
    Path(r"C:\Program Files\Deltares"),
)
WANDA_BIN_ENV_VAR = "PYWANDAHYDRA_WANDA_BIN"


def _version_key(install_name: str) -> tuple[int, ...]:
    """Sortable version tuple from an install dir name like 'Wanda 4.8'."""
    return tuple(int(part) for part in re.findall(r"\d+", install_name))


def find_wanda_bin() -> Path:
    """Locate WANDA installation, preferring env var, then auto-discovery."""
    env_value = os.environ.get(WANDA_BIN_ENV_VAR)
    if env_value:
        return Path(env_value)

    candidates: list[tuple[tuple[int, ...], int, Path]] = []
    for root in _SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for install in root.glob("Wanda *"):
            for preference, bin_name in enumerate(("Bin", "Bin64")):
                bin_dir = install / bin_name
                if bin_dir.is_dir():
                    candidates.append((_version_key(install.name), preference, bin_dir))

    if not candidates:
        raise FileNotFoundError(
            "No WANDA installation found under "
            + " or ".join(str(root) for root in _SEARCH_ROOTS)
            + f". Install WANDA or set {WANDA_BIN_ENV_VAR} to the bin directory."
        )

    return max(candidates)[2]


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture
def make_scenario() -> Callable[..., ScenarioSpecification]:
    def _factory(
        name: str = "case_001", number: int = 1, include: bool = True
    ) -> ScenarioSpecification:
        return ScenarioSpecification(number=number, include=include, name=name)

    return _factory

