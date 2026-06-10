"""Post-processing methodologies — pluggable analysis strategies.

A methodology defines *which* post-processing steps to run and in what
order for a given case.

Usage:
    1. Create a class implementing the :class:`Methodology` protocol.
    2. Register it with :func:`register_methodology`.
    3. Reference it by name in the run config.

Built-in methodologies are registered via :func:`bootstrap`, which must
be called once per process (idempotent, safe to call repeatedly).
"""

from .base import (
    Methodology,
    get_methodology,
    list_methodologies,
    register_methodology,
)
from .default import DefaultMethodology


def bootstrap() -> None:
    """Register all built-in methodologies.

    Idempotent: safe to call from every worker process under multiprocessing
    ``spawn`` start method, and safe to call multiple times in the same
    process. Tests can call this to ensure a clean registration state.
    """
    register_methodology(DefaultMethodology())


__all__ = [
    "DefaultMethodology",
    "Methodology",
    "bootstrap",
    "get_methodology",
    "list_methodologies",
    "register_methodology",
]
