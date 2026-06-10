"""Methodology protocol and registry."""

from __future__ import annotations

import logging
from typing import Dict, Protocol, runtime_checkable

from ..pipeline import PostProcessingContext, PostProcessor

logger = logging.getLogger(__name__)


@runtime_checkable
class Methodology(Protocol):
    """Protocol for a post-processing methodology.

    A methodology assembles and configures a sequence of post-processing
    steps appropriate for a specific analysis approach.

    Attributes:
        name: Unique identifier for this methodology.
        description: Human-readable description of the methodology.
    """

    name: str
    description: str

    def get_steps(self, ctx: PostProcessingContext) -> list[PostProcessor]:
        """Return the ordered list of steps for this methodology.

        The methodology can inspect the context (scenario spec, cache
        contents) to conditionally include or parameterize steps.

        Args:
            ctx: The post-processing context for the current case.

        Returns:
            Ordered list of step instances to execute.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_METHODOLOGIES: Dict[str, Methodology] = {}


def register_methodology(methodology: Methodology) -> Methodology:
    """Register a methodology in the global registry.

    Idempotent: registering an instance under a name that already exists
    is a no-op and returns the already-registered instance. This keeps
    bootstrap() safe to call from multiple worker processes (spawn).

    Args:
        methodology: An instance implementing the Methodology protocol.

    Returns:
        The registered Methodology instance (existing one on duplicate).
    """
    existing = _METHODOLOGIES.get(methodology.name)
    if existing is not None:
        return existing
    _METHODOLOGIES[methodology.name] = methodology
    logger.debug("Registered methodology: %s", methodology.name)
    return methodology


def get_methodology(name: str) -> Methodology:
    """Look up a registered methodology by name.

    Args:
        name: The methodology name (case-sensitive).

    Returns:
        The registered Methodology instance.

    Raises:
        KeyError: If no methodology is registered under that name.
    """
    if name not in _METHODOLOGIES:
        available = sorted(_METHODOLOGIES.keys())
        raise KeyError(f"Unknown methodology: '{name}'. Available: {available}")
    return _METHODOLOGIES[name]


def list_methodologies() -> list[str]:
    """Return names of all registered methodologies."""
    return sorted(_METHODOLOGIES.keys())
