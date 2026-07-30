"""Route tracing and orientation helpers for WANDA components."""

from __future__ import annotations

import logging
from typing import Any

import pywanda

from .item_lookup import resolve_items

logger = logging.getLogger("pywandahydra.wanda.api")


def _get_connected_nodes(component: Any) -> dict[int, Any]:
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
    if len(components) <= 1:
        return components

    component_graph = _build_component_graph(components)
    if not component_graph:
        return components

    endpoints = [
        component for component, neighbours in component_graph.items() if len(neighbours) <= 1
    ]

    start = endpoints[0] if endpoints else components[0]
    end = endpoints[1] if len(endpoints) > 1 else components[-1]

    route = _find_route(component_graph, start, end)
    if not route:
        logger.warning(
            "No connected path found between route components – returning in original order."
        )
        return components

    if len(route) == len(components):
        return route

    missing = [component for component in components if component not in route]
    return route + missing


def _components_form_connected_path(components: list[Any]) -> bool:
    if len(components) <= 1:
        return True

    component_graph = _build_component_graph(components)
    if not component_graph:
        return False

    adjacency: dict[Any, set[Any]] = {component: set() for component in components}
    for component, neighbours in component_graph.items():
        for neighbour in neighbours:
            adjacency[component].add(neighbour)
            adjacency[neighbour].add(component)

    start = components[0]
    seen = {start}
    stack = [start]
    while stack:
        current = stack.pop()
        for neighbour in adjacency[current]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)

    return len(seen) == len(components)


def _normalize_pipe_route_orientation(
    pipes_with_direction: list[tuple[Any, int]],
) -> list[tuple[Any, int]]:
    if not pipes_with_direction:
        return pipes_with_direction

    if all(direction < 0 for _, direction in pipes_with_direction):
        return [(pipe, -direction) for pipe, direction in reversed(pipes_with_direction)]

    return pipes_with_direction


def _pipe_name(pipe: Any) -> str:
    if hasattr(pipe, "get_complete_name_spec"):
        return str(pipe.get_complete_name_spec())
    return str(pipe)


def resolve_route_pipes(
    model: pywanda.WandaModel,
    route_id: str,
) -> list[tuple[str, int]]:
    """Resolve route pipes as ``(pipe_name, direction)`` tuples."""
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
    except (RuntimeError, ValueError):
        logger.error(
            "Route '%s' could not be resolved via get_route – falling back to item resolution.",
            route_id,
            exc_info=True,
        )
        items = resolve_items(model, route_id)
        pipe_components = []
        for ref in items:
            if ref.type != "component":
                continue
            try:
                comp = model.get_component(ref.name)
            except Exception:
                continue
            if hasattr(comp, "is_pipe") and comp.is_pipe():
                pipe_components.append(comp)
        if not pipe_components:
            return []
        if len(pipe_components) == 1:
            return [(_pipe_name(pipe_components[0]), 1)]
        if not _components_form_connected_path(pipe_components):
            logger.error(
                "Route '%s' resolved to disconnected pipes (gap between waypoints) – skipping.",
                route_id,
            )
            return []
        ordered = _order_components_by_connection(pipe_components)
        return [(_pipe_name(comp), 1) for comp in ordered]

    return []
