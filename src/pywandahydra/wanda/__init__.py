"""WANDA integration package interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_access import WandaModelAccess

if TYPE_CHECKING:
    from .session import wanda_session


def __getattr__(name: str) -> Any:
    """Load the pywanda-backed session helper only when a caller requests it."""
    if name == "wanda_session":
        from .session import wanda_session

        return wanda_session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["WandaModelAccess", "wanda_session"]
