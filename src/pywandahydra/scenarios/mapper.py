"""Compatibility facade for scenario loading functions.

Slice 04 moved source dispatch to ``scenarios.loader`` and introduced
``ScenarioDocument`` as the authoritative workbook aggregate.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .loader import (
    ScenarioLoadOptions,
    assert_scenario_file_valid,
    check_scenario_file,
    load_scenario_document,
)
from .models.document import ScenarioDocument
from .schema import ScenarioSpecification

logger = logging.getLogger(__name__)


def load_scenarios(
    path: Path | str,
    *,
    options: ScenarioLoadOptions | None = None,
) -> list[ScenarioSpecification]:
    """Load all valid scenarios from a file (include filtering is deferred)."""
    document = load_scenario_document(path, options=options)
    scenarios = list(document.scenarios)
    logger.info("Loaded %d scenarios from %s", len(scenarios), document.source_path.name)
    return scenarios


__all__ = [
    "ScenarioLoadOptions",
    "ScenarioDocument",
    "load_scenarios",
    "load_scenario_document",
    "check_scenario_file",
    "assert_scenario_file_valid",
]
