"""WANDA parameter application and unit conversion helpers."""

from __future__ import annotations

from typing import Any

import pywanda

from ..disuse import parse_disuse_value
from ..scenarios.schema import ModelParameterChange
from .item_lookup import get_item, resolve_items


class ParameterApplicationError(RuntimeError):
    """Raised when a parameter change cannot be applied to a Wanda model."""


def to_model_units(value: float, prop: Any) -> float:
    """Convert a value from SI units to the model's native units."""
    unit_factor = float(prop.get_unit_factor())
    if unit_factor > 0.0:
        return value / unit_factor
    return value


def to_si_units(value: Any, prop: Any) -> Any:
    """Convert a value from model units to SI units."""
    return value * float(prop.get_unit_factor())


def apply_parameter_change(model: pywanda.WandaModel, change: ModelParameterChange) -> None:
    """Apply a parameter change to a Wanda model."""
    try:
        if change.component.lower() == "general":
            prop = model.get_property(change.property)
            prop.set_scalar(change.value)
            return

        item_refs = resolve_items(model, change.component)
        if not item_refs:
            raise ParameterApplicationError(f"Component '{change.component}' not found")

        if change.property.lower() == "disuse":
            disuse_value = parse_disuse_value(change.value)
            for item_ref in item_refs:
                item = get_item(model, item_ref)
                item.set_disused(disuse_value)
            return

        for item_ref in item_refs:
            item = get_item(model, item_ref)
            prop = item.get_property(change.property)
            prop.set_scalar(to_model_units(change.value, prop))

    except Exception as e:
        raise ParameterApplicationError(
            f"Failed to apply {change.component}.{change.property}={change.value!r}: {e}"
        ) from e
