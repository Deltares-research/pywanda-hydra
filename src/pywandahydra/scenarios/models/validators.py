"""Shared normalization and validation helpers for scenario models."""

from __future__ import annotations

from typing import Any


def ensure_non_empty_string(value: Any, *, field_name: str = "value") -> str:
    """Return a stripped non-empty string or raise ValueError."""
    s = str(value).strip()
    if not s:
        raise ValueError(f"{field_name} must be a non-empty string")
    return s


def normalize_fig(value: Any) -> str | None:
    """Normalize figure identifier values from XLS cells."""
    if value is None:
        return None
    if isinstance(value, float):
        import math

        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
    s = str(value).strip()
    return s or None


def normalize_optional_int(value: Any, *, field_name: str) -> int | None:
    """Normalize optional integer-like values from XLS cells."""
    if value is None:
        return None
    if isinstance(value, float):
        import math

        if math.isnan(value):
            return None
        if value.is_integer():
            return int(value)
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    return None


def normalize_optional_float(value: Any, *, field_name: str) -> float | None:
    """Normalize optional float-like values from XLS cells."""
    if value is None:
        return None
    if isinstance(value, float):
        import math

        if math.isnan(value):
            return None
        return float(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be numeric") from exc
    raise ValueError(f"{field_name} must be numeric")
