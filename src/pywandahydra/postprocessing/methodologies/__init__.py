"""Post-processing methodologies — pluggable analysis strategies.

A methodology defines *which* post-processing steps to run and in what
order for a given case.

Usage:
    1. Create a class implementing the :class:`Methodology` protocol.
    2. Register it with :func:`register_methodology`.
    3. Reference it by name in the run config.
"""

from .base import (
    Methodology,
    get_methodology,
    list_methodologies,
    register_methodology,
)

__all__ = [
    "Methodology",
    "get_methodology",
    "list_methodologies",
    "register_methodology",
]
