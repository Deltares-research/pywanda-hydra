"""Scenario source implementations.

This package contains built-in parser functions; loader dispatch is defined in
``pywandahydra.scenarios.loader``.
"""

from .xls import check_xls_structure, load_excel_document, read_scenarios_from_excel

__all__ = [
    "check_xls_structure",
    "load_excel_document",
    "read_scenarios_from_excel",
]
