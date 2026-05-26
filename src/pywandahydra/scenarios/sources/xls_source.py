"""XLS/XLSX scenario source — wraps the existing Excel parser."""

from __future__ import annotations

from pathlib import Path

from ..schema import ScenarioSpecification
from .base import register_source
from .xls import read_scenarios_from_excel


@register_source
class XlsScenarioSource:
    """Scenario source for Excel files (.xls, .xlsx, .xlsm).

    Wraps the existing ``read_scenarios_from_excel`` parser behind the
    ``ScenarioSource`` protocol.
    """

    extensions: set[str] = {".xls", ".xlsx", ".xlsm"}

    def __init__(self, options: "ScenarioLoadOptions | None" = None) -> None:
        from ..mapper import ScenarioLoadOptions

        self.options = options or ScenarioLoadOptions()

    def load(self, path: Path) -> list[ScenarioSpecification]:
        """Load scenarios from an Excel workbook.

        Args:
            path: Path to the .xls/.xlsx/.xlsm file.

        Returns:
            List of scenario specifications.
        """
        return read_scenarios_from_excel(path, self.options)
