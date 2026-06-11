"""Custom model-level extraction plugins.

Extractors allow users to pull additional data from open WANDA models before
postprocessing begins. They run sequentially during model execution and their
outputs are cached alongside standard extraction results.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Registry for extractor classes
_EXTRACTOR_CLASSES: dict[str, type[Any]] = {}


@runtime_checkable
class Extractor(Protocol):
    """Protocol for custom model-level extraction plugins.

    Extractors run after the WANDA model has been simulated but before
    the model session closes. They receive full model access and can extract
    any additional data beyond the standard component/route outputs.

    Example:
        class MyEnergyExtractor:
            name = "my_energy_extractor"
            class Params(BaseModel):
                threshold: float = 100.0
            def __init__(self, params: Params | None = None) -> None:
                self._p = params or self.Params()
            def extract(self, ctx: ExtractionContext) -> dict[str, Any]:
                # Access ctx.model, ctx.adapter, ctx.scenario
                # Compute and return custom DataFrames
                return {"energy_loss": df}
    """

    name: ClassVar[str]
    """Unique identifier for this extractor (used as cache key)."""

    description: ClassVar[str]
    """Human-readable description of what this extractor does."""

    Params: ClassVar[type[BaseModel]]
    """Pydantic model for extractor parameters."""

    def __init__(self, params: BaseModel | None = None) -> None:
        """Initialize extractor with optional parameters.

        Args:
            params: Validated Params instance, or None for defaults.
        """
        ...

    def extract(self, ctx: ExtractionContext) -> dict[str, Any]:
        """Extract custom data from the live model.

        Args:
            ctx: ExtractionContext with model, adapter, scenario, and case paths.

        Returns:
            Dict mapping output names to pandas DataFrames or nested structures.
            Examples:
                {"pressure_stats": df}  # Persists as pressure_stats.parquet
                {"route_data": {"timeseries": df, "profile": df}}  # Nested (like routes)

            Empty dict if no data extracted (e.g., no matching routes).
        """
        ...


def register_extractor(extractor_class: type[Any]) -> type[Any]:
    """Register an extractor class by its declared name.

    Args:
        extractor_class: Class implementing the Extractor protocol.

    Returns:
        The registered class.
    """
    existing = _EXTRACTOR_CLASSES.get(extractor_class.name)
    if existing is not None:
        return existing
    _EXTRACTOR_CLASSES[extractor_class.name] = extractor_class
    logger.debug("Registered extractor: %s", extractor_class.name)
    return extractor_class


def get_extractor_class(name: str) -> type[Any]:
    """Look up a registered extractor class by name.

    Args:
        name: Extractor name.

    Returns:
        The extractor class.

    Raises:
        KeyError: If extractor not found.
    """
    if name not in _EXTRACTOR_CLASSES:
        available = sorted(_EXTRACTOR_CLASSES.keys())
        raise KeyError(f"Unknown extractor: '{name}'. Available: {available}")
    return _EXTRACTOR_CLASSES[name]


def list_extractors() -> list[str]:
    """Return names of all registered extractors (sorted).

    Returns:
        List of extractor names.
    """
    return sorted(_EXTRACTOR_CLASSES.keys())


def resolve_extractor(name: str, params: dict[str, Any] | None = None) -> Extractor:
    """Instantiate a registered extractor with validated parameters.

    Args:
        name: Extractor name.
        params: Dict of parameters (will be validated against Params schema).

    Returns:
        Extractor instance.

    Raises:
        KeyError: If extractor not registered.
        ValidationError: If params don't match schema.
    """
    from typing import cast

    cls = get_extractor_class(name)
    validated = cls.Params.model_validate(params or {})
    return cast(Extractor, cls(validated))
