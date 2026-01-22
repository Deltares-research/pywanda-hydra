"""Wanda API utilities for applying parameter changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pywanda

from ..scenarios.schema import ParameterChange

ItemType = Literal["component", "node", "signal_line"]


@dataclass(frozen=True)
class WandaItemRef:
    """Reference to a Wanda model item (component, node, or signal line).

    Attributes
    ----------
    name : str
        The complete name specification of the item.
    type : ItemType
        The type of the item: "component", "node", or "signal_line".
    """

    name: str  # complete_name_spec (preferred)
    type: ItemType


def get_item(model: pywanda.WandaModel, ref: WandaItemRef) -> Any:
    """Serialize reference to a Wanda model item.

    Parameters
    ----------
    model : pywanda.WandaModel
        The Wanda model instance.
    ref : WandaItemRef
        The reference to the item.
    Returns
    -------
    Any
        The referenced item from the Wanda model.
    """
    if ref.type == "component":
        return model.get_component(ref.name)
    if ref.type == "node":
        return model.get_node(ref.name)
    if ref.type == "signal_line":
        return model.get_signal_line(ref.name)
    raise ValueError(f"Unknown item type: {ref.type}")


def find_items_with_keyword(model: pywanda.WandaModel, keyword: str) -> list[WandaItemRef]:
    """Find items in the Wanda model matching a keyword.

    Parameters
    ----------
    model : pywanda.WandaModel
        The Wanda model instance.
    keyword : str
        The keyword to search for in item names.

    Returns
    -------
    list[WandaItemRef]
        List of item references matching the keyword.
    """
    keyword = str(keyword).strip()

    if not keyword:
        return []

    matched_items: list[WandaItemRef] = []

    # Search components
    matched_items.extend(
        [
            WandaItemRef(comp_name, "component")
            for comp_name in model.get_components_name_with_keyword(keyword)
        ]
    )

    # Search nodes
    matched_items.extend(
        [
            WandaItemRef(node_name, "node")
            for node_name in model.get_node_names_with_keyword(keyword)
        ]
    )

    # Search signal lines
    matched_items.extend(
        [
            WandaItemRef(sig_name, "signal_line")
            for sig_name in model.get_signal_line_names_with_keyword(keyword)
        ]
    )

    return matched_items


def signal_line_exists(model: pywanda.WandaModel, name: str) -> bool:
    """Check if a signal line exists in the Wanda model.

    Parameters
    ----------
    model : pywanda.WandaModel
        The Wanda model instance.
    name : str
        The name of the signal line.

    Returns
    -------
    bool
        True if the signal line exists, False otherwise.
    """
    try:
        model.get_signal_line(name)
        return True
    except Exception:
        return False


def resolve_items(
    model: pywanda.WandaModel,
    identifier: str,
) -> list[WandaItemRef]:
    """Resolve item references from an identifier.

    Methodology:
    1. Exact node match if identifier matches node style (e.g. "H-node" in name).
    2. Exact signal line match if identifier matches signal line style (e.g. "Signal" in name).
    3. Exact component match.
    4. Keyword search across all item types if no exact match found.

    Parameters
    ----------
    model : pywanda.WandaModel
        The Wanda model instance.
    identifier : str
        The identifier to resolve (could be exact name or keyword).

    Returns
    -------
    list[WandaItemRef]
        List of resolved item references.
    """
    identifier = str(identifier).strip()
    if not identifier:
        return []

    # Determine type hint from identifier pattern
    type_identifier = identifier.split(" ", maxsplit=1)[0]

    # Node
    if type_identifier.startswith("H-node") and model.node_exists(identifier):
        node = model.get_node(identifier)
        return [WandaItemRef(node.get_complete_name_spec(), "node")]

    # Signal line (heuristic; adapt to your naming conventions)
    if type_identifier.startswith("Signal") and signal_line_exists(model, identifier):
        sig = model.get_signal_line(identifier)
        return [WandaItemRef(sig.get_complete_name_spec(), "signal_line")]

    # Component
    if model.component_exists(identifier):
        comp = model.get_component(identifier)
        return [WandaItemRef(comp.get_complete_name_spec(), "component")]

    # Fallback: keyword
    return find_items_with_keyword(model, identifier)


def apply_parameter_change(model: pywanda.WandaModel, change: ParameterChange) -> None:
    """Apply a parameter change to a Wanda model.

    Parameters
    ----------
    model : pywanda.WandaModel
        The Wanda model instance to modify.
    change : ParameterChange
        The parameter change to apply.

    Returns
    -------
    None
    """
    try:
        # General property set
        if change.component.lower() == "general":
            prop = model.get_property(change.property)
            prop.set_scalar(change.value)
            return

        # Get items
        item_refs = resolve_items(model, change.component)
        if not item_refs:
            raise Exception(f"Component '{change.component}' not found")

        # Handling of 'disuse' property
        if change.property.lower() == "disuse":
            # Set disuse on all matched items
            for item_ref in item_refs:
                item = get_item(model, item_ref)
                item.set_disused(bool(change.value))
            return

        # Apply change to all matched items
        for item_ref in item_refs:
            item = get_item(model, item_ref)
            prop = item.get_property(change.property)
            # Handle unit factors if required
            if prop.get_unit_factor() > 0.0:
                prop.set_scalar(change.value / prop.get_unit_factor())
            else:
                prop.set_scalar(change.value)

    except Exception as e:
        raise Exception(
            f"Failed to apply {change.component}.{change.property}={change.value!r}: {e}"
        ) from e
