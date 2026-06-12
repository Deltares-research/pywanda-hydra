"""Utilities for parsing legacy Disuse input semantics."""

from __future__ import annotations

from typing import Any


def parse_disuse_value(value: Any) -> bool:
    """Parse legacy Disuse values to the boolean expected by WANDA.

    Legacy semantics:
    - Disused: 0, 0.0, "0", yes, true, y, disuse
    - In use:  1, 1.0, "1", no, false, n, use
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        token = value.strip().lower()
        if token in ("0", "yes", "true", "y", "disuse"):
            return True
        if token in ("1", "no", "false", "n", "use"):
            return False
        raise ValueError(
            f"Cannot normalize string {value!r} to boolean for 'disuse' property"
        )

    if isinstance(value, int | float):
        if value == 0 or value == 0.0:
            return True
        if value == 1 or value == 1.0:
            return False
        raise ValueError(
            f"Cannot normalize numeric value {value!r} to boolean for 'disuse' property"
        )

    raise ValueError(
        f"Cannot normalize value of type '{type(value)}' to boolean for 'disuse' property"
    )
