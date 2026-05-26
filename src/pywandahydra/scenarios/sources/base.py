"""Base protocol and registry for scenario sources."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..schema import ScenarioSpecification


@runtime_checkable
class ScenarioSource(Protocol):
    """Protocol for scenario loading backends.

    Implementations must provide:
    - ``extensions``: set of file extensions this source handles (e.g. {".xls", ".xlsx"})
    - ``load``: parse the file and return scenario specifications
    """

    extensions: set[str]

    def load(self, path: Path) -> list[ScenarioSpecification]:
        """Load scenarios from the given file path.

        Args:
            path: Path to the scenario definition file.

        Returns:
            List of parsed scenario specifications.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[ScenarioSource]] = {}


def register_source(source_cls: type[ScenarioSource]) -> type[ScenarioSource]:
    """Register a ScenarioSource class for its declared extensions.

    Can be used as a decorator::

        @register_source
        class XlsSource:
            extensions = {".xls", ".xlsx", ".xlsm"}
            ...

    Args:
        source_cls: The source class to register.

    Returns:
        The same class, unmodified.
    """
    for ext in source_cls.extensions:
        _REGISTRY[ext.lower()] = source_cls
    return source_cls


def get_source_for_extension(ext: str) -> type[ScenarioSource]:
    """Look up the registered ScenarioSource for a file extension.

    Args:
        ext: File extension including the dot (e.g. ".xlsx").

    Returns:
        The registered source class.

    Raises:
        ValueError: If no source is registered for the given extension.
    """
    ext = ext.lower()
    if ext not in _REGISTRY:
        supported = sorted(_REGISTRY.keys())
        raise ValueError(
            f"Unsupported scenario file extension: '{ext}'. "
            f"Supported: {supported}"
        )
    return _REGISTRY[ext]
