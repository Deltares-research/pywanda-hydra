"""Wanda API utilities for applying parameter changes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pywanda

from ..disuse import parse_disuse_value
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


def find_items_with_keyword(
    model: pywanda.WandaModel, keyword: str
) -> list[WandaItemRef]:
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


# ---------------------------------------------------------------------------
# Bulk selectors: special identifiers that expand to groups of items
# ---------------------------------------------------------------------------


def _all_pipes(model: pywanda.WandaModel) -> list[WandaItemRef]:
    """Return references to all pipe components in the model."""
    return [
        WandaItemRef(pipe.get_complete_name_spec(), "component")
        for pipe in model.get_all_pipes()
    ]


def _all_components(model: pywanda.WandaModel) -> list[WandaItemRef]:
    """Return references to all components in the model."""
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
    """Resolve item references from an identifier.

    Resolution order:
    0. Bulk selectors: ``PALL`` (all pipes), ``CALL`` (all components).
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

    # Bulk selectors (e.g. "PALL" = all pipes)
    upper = identifier.upper()
    if upper in _BULK_SELECTORS:
        return _BULK_SELECTORS[upper](model)

    # Determine type hint from identifier pattern
    type_identifier = identifier.split(" ", maxsplit=1)[0]

    # Node
    if type_identifier.startswith("H-node") and model.node_exists(identifier):
        node = model.get_node(identifier)
        return [WandaItemRef(node.get_complete_name_spec(), "node")]

    # Signal line (heuristic; adapt to your naming conventions)
    if type_identifier.startswith("Signal") and model.sig_line_exists(identifier):
        sig = model.get_signal_line(identifier)
        return [WandaItemRef(sig.get_complete_name_spec(), "signal_line")]

    # Component
    if model.component_exists(identifier):
        comp = model.get_component(identifier)
        return [WandaItemRef(comp.get_complete_name_spec(), "component")]

    # Fallback: keyword
    return find_items_with_keyword(model, identifier)


def _get_connected_nodes(component: Any) -> dict[int, Any]:
    """Get connected nodes for a component using node identifiers 1..9."""
    connected_nodes: dict[int, Any] = {}
    for node_id in range(1, 10):
        try:
            connected_nodes[node_id] = component.get_connected_node(node_id)
        except Exception:
            return connected_nodes
    return connected_nodes


def _get_connected_components(
    component: Any,
    connected_nodes: dict[int, Any],
    *,
    allowed: set[Any] | None = None,
) -> dict[Any, dict[int, Any]]:
    """Map connected components to connecting node metadata."""
    connected_components: dict[Any, dict[int, Any]] = {}
    for node_id, connected_node in connected_nodes.items():
        try:
            node_components = connected_node.get_connected_components()
        except Exception:
            continue
        for comp in node_components:
            if comp == component:
                continue
            if allowed is not None and comp not in allowed:
                continue
            if comp not in connected_components:
                connected_components[comp] = {node_id: connected_node}
    return connected_components


def _find_route(
    component_graph: dict[Any, dict[Any, dict[int, Any]]],
    start_component: Any,
    end_component: Any,
    visited: set[Any] | None = None,
    route: list[Any] | None = None,
) -> list[Any] | None:
    """Find a route between two components using depth-first traversal."""
    if visited is None:
        visited = set()
    if route is None:
        route = []

    visited.add(start_component)
    route.append(start_component)

    if start_component == end_component:
        return route

    for connected_component in component_graph.get(start_component, {}):
        if connected_component not in visited:
            new_route = _find_route(
                component_graph,
                connected_component,
                end_component,
                visited.copy(),
                route.copy(),
            )
            if new_route:
                return new_route
    return None


def _connection_node_id(component: Any, neighbour: Any) -> int | None:
    """Return the node id on *component* that connects to *neighbour*."""
    connected_nodes = _get_connected_nodes(component)
    for node_id, node in connected_nodes.items():
        try:
            connected_components = node.get_connected_components()
        except Exception:
            continue
        for comp in connected_components:
            if comp == neighbour:
                return node_id
    return None


def _pipe_direction_from_route_component_index(
    route_components: list[Any],
    idx: int,
) -> int:
    """Infer direction from route neighbours using node-id semantics.

    Node id ``1`` means reverse traversal and node id ``2`` means forward.
    """
    component = route_components[idx]
    if idx < len(route_components) - 1:
        neighbour = route_components[idx + 1]
    elif idx > 0:
        neighbour = route_components[idx - 1]
    else:
        return 1

    node_id = _connection_node_id(component, neighbour)
    if node_id == 1:
        return -1
    if node_id == 2:
        return 1
    return 1


def _build_component_graph(
    components: list[Any],
) -> dict[Any, dict[Any, dict[int, Any]]]:
    """Build a connection graph for the given components."""
    allowed = set(components)
    component_graph: dict[Any, dict[Any, dict[int, Any]]] = {}
    for component in components:
        connected_nodes = _get_connected_nodes(component)
        connected_components = _get_connected_components(
            component,
            connected_nodes,
            allowed=allowed,
        )
        component_graph[component] = connected_components
    return component_graph


def _order_components_by_connection(components: list[Any]) -> list[Any]:
    """Return components ordered by connectivity along a route-like path."""
    if len(components) <= 1:
        return components

    component_graph = _build_component_graph(components)
    if not component_graph:
        return components

    endpoints = [
        component
        for component, neighbours in component_graph.items()
        if len(neighbours) <= 1
    ]

    start = endpoints[0] if endpoints else components[0]
    end = endpoints[1] if len(endpoints) > 1 else components[-1]

    route = _find_route(component_graph, start, end)
    if not route:
        return components

    if len(route) == len(components):
        return route

    # Preserve all original components even if route traversal did not span all.
    missing = [component for component in components if component not in route]
    return route + missing


def _normalize_pipe_route_orientation(
    pipes_with_direction: list[tuple[Any, int]],
) -> list[tuple[Any, int]]:
    """Normalize route orientation to avoid per-pipe flips on fully reversed routes.

    When every resolved pipe direction is ``-1``, the route is globally reversed.
    In that case we flip the route as a whole by reversing pipe order and inverting
    direction signs. This preserves pipe-to-pipe continuity while keeping the
    traversal direction aligned with connectivity.
    """
    if not pipes_with_direction:
        return pipes_with_direction

    if all(direction < 0 for _, direction in pipes_with_direction):
        return [
            (pipe, -direction) for pipe, direction in reversed(pipes_with_direction)
        ]

    return pipes_with_direction


def _pipe_name(pipe: Any) -> str:
    """Return a stable component name for a pipe-like object."""
    if hasattr(pipe, "get_complete_name_spec"):
        return str(pipe.get_complete_name_spec())
    return str(pipe)


def resolve_route_pipes(
    model: pywanda.WandaModel,
    route_id: str,
) -> list[tuple[str, int]]:
    """Resolve route pipes as ``(pipe_name, direction)`` tuples.

    Preferred path uses ``model.get_route``. When route direction is not usable,
    orientation is inferred from component connectivity. Fallback resolution uses
    ``resolve_items`` and route traversal between the first and last items.
    """
    route_id = str(route_id).strip()
    if not route_id:
        return []

    try:
        components, directions = model.get_route(route_id)
        raw_components = list(components)
        comps = _order_components_by_connection(raw_components)
        dirs = list(directions)
        direction_by_component: dict[Any, int] = {}
        for comp, direction in zip(raw_components, dirs, strict=True):
            if not (hasattr(comp, "is_pipe") and comp.is_pipe()):
                continue
            if int(direction) == 0:
                continue
            direction_by_component[comp] = 1 if int(direction) > 0 else -1

        ordered_pipes: list[tuple[Any, int]] = []
        for idx, comp in enumerate(comps):
            if hasattr(comp, "is_pipe") and comp.is_pipe():
                direction = direction_by_component.get(comp)
                if direction is None:
                    direction = _pipe_direction_from_route_component_index(comps, idx)
                ordered_pipes.append((comp, direction))
        if ordered_pipes:
            normalized = _normalize_pipe_route_orientation(ordered_pipes)
            return [(_pipe_name(pipe), direction) for pipe, direction in normalized]
    except Exception:
        pass

    item_refs = resolve_items(model, route_id)
    items: list[Any] = []
    for ref in item_refs:
        try:
            item = get_item(model, ref)
        except Exception:
            continue
        items.append(item)

    if not items:
        return []

    if len(items) == 1:
        item = items[0]
        if hasattr(item, "is_pipe") and item.is_pipe():
            return [(_pipe_name(item), 1)]
        return []

    route = _order_components_by_connection(items)

    fallback_pipes: list[tuple[Any, int]] = []
    for idx, component in enumerate(route):
        if hasattr(component, "is_pipe") and component.is_pipe():
            direction = _pipe_direction_from_route_component_index(route, idx)
            fallback_pipes.append((component, direction))
    normalized = _normalize_pipe_route_orientation(fallback_pipes)
    return [(_pipe_name(pipe), direction) for pipe, direction in normalized]


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
            disuse_value = parse_disuse_value(change.value)
            for item_ref in item_refs:
                item = get_item(model, item_ref)
                item.set_disused(disuse_value)
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
