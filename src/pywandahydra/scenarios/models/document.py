"""Scenario workbook document aggregate models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .meta import AnalysisMeta
from .scenario import ScenarioSpecification


@dataclass(frozen=True, slots=True)
class ScenarioWarning:
    """Typed warning emitted while reading or validating a scenario document."""

    sheet: str
    message: str
    row: int | None = None
    column: str | None = None


class ScenarioDocument(BaseModel):
    """Scenario workbook document containing metadata, scenarios, and warnings."""

    model_config = ConfigDict(extra="forbid")

    analysis_metadata: AnalysisMeta
    scenarios: tuple[ScenarioSpecification, ...]
    source_path: Path
    warnings: tuple[ScenarioWarning, ...] = ()
