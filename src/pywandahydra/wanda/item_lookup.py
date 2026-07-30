"""WANDA item lookup and identifier resolution helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pywanda

ItemType = Literal["component", "node", "signal_line"]


@dataclass(frozen=True)
class WandaItemRef:
    """Reference to a Wanda model item (component, node, or signal line)."""

    name: str
    type: ItemType


def get_item(model: pywanda.WandaModel, ref: WandaItemRef) -> Any:
    """Return the referenced model item."""
    if ref.type == "component":
        return model.get_component(ref.name)
    if ref.type == "node":
        return model.get_node(ref.name)
    if ref.type == "signal_line":
        return model.get_signal_line(ref.name)
    raise ValueError(f"Unknown item type: {ref.type}")


def find_items_with_keyword(model: pywanda.WandaModel, keyword: str) -> list[WandaItemRef]:
    """Find items in the Wanda model matching a keyword."""
    keyword = str(keyword).strip()
    if not keyword:
        return []

    matched_items: list[WandaItemRef] = []
    matched_items.extend(
        [
            WandaItemRef(comp_name, "component")
            for comp_name in model.get_components_name_with_keyword(keyword)
        ]
    )
    matched_items.extend(
        [
            WandaItemRef(node_name, "node")
            for node_name in model.get_node_names_with_keyword(keyword)
        ]
    )
    matched_items.extend(
        [
            WandaItemRef(sig_name, "signal_line")
            for sig_name in model.get_signal_line_names_with_keyword(keyword)
        ]
    )
    return matched_items


def _all_pipes(model: pywanda.WandaModel) -> list[WandaItemRef]:
    return [
        WandaItemRef(pipe.get_complete_name_spec(), "component") for pipe in model.get_all_pipes()
    ]


def _all_components(model: pywanda.WandaModel) -> list[WandaItemRef]:
    return [
        WandaItemRef(comp.get_complete_name_spec(), "component")
        for comp in model.get_all_components()
    ]


_BulkSelector = Callable[[pywanda.WandaModel], list[WandaItemRef]]

_BULK_SELECTORS: dict[str, _BulkSelector] = {
    "PALL": _all_pipes,
    "CALL": _all_components,
}


def resolve_items(
    model: pywanda.WandaModel,
    identifier: str,
) -> list[WandaItemRef]:
    """Resolve item references from an identifier."""
    identifier = str(identifier).strip()
    if not identifier:
        return []

    upper = identifier.upper()
    if upper in _BULK_SELECTORS:
        return _BULK_SELECTORS[upper](model)

    type_identifier = identifier.split(" ", maxsplit=1)[0]

    if type_identifier.startswith("H-node") and model.node_exists(identifier):
        node = model.get_node(identifier)
        return [WandaItemRef(node.get_complete_name_spec(), "node")]

    if type_identifier.startswith("Signal") and model.sig_line_exists(identifier):
        sig = model.get_signal_line(identifier)
        return [WandaItemRef(sig.get_complete_name_spec(), "signal_line")]

    if model.component_exists(identifier):
        comp = model.get_component(identifier)
        return [WandaItemRef(comp.get_complete_name_spec(), "component")]

    return find_items_with_keyword(model, identifier)
