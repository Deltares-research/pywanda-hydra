"""Unit tests for the pure resolution/conversion logic in wanda.api.

These tests use lightweight fake model/component/node objects so that
the routing and unit-conversion logic can be exercised without a live
WANDA session.
"""

from __future__ import annotations

import unittest

from pywandahydra.scenarios import ModelParameterChange
from pywandahydra.wanda.api import (
    ParameterApplicationError,
    WandaItemRef,
    _connection_node_id,
    _find_route,
    _get_connected_components,
    _get_connected_nodes,
    _normalize_pipe_route_orientation,
    _order_components_by_connection,
    _pipe_direction_from_route_component_index,
    _pipe_name,
    apply_parameter_change,
    find_items_with_keyword,
    resolve_items,
    resolve_route_pipes,
    to_model_units,
    to_si_units,
)


class _FakeProp:
    def __init__(self, unit_factor: float = 1.0) -> None:
        self.unit_factor = unit_factor
        self.scalar: float | None = None

    def get_unit_factor(self) -> float:
        return self.unit_factor

    def set_scalar(self, value: float) -> None:
        self.scalar = value

    def get_scalar_float(self) -> float:
        return self.scalar  # type: ignore[return-value]


class _FakeNode:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected_components: list[_FakeComponent] = []

    def get_connected_components(self) -> list[_FakeComponent]:
        return self.connected_components

    def get_complete_name_spec(self) -> str:
        return self.name


class _FakeComponent:
    def __init__(self, name: str, *, is_pipe: bool = True) -> None:
        self.name = name
        self._is_pipe = is_pipe
        self.nodes: dict[int, _FakeNode] = {}
        self.properties: dict[str, _FakeProp] = {}
        self.disused = False

    def is_pipe(self) -> bool:
        return self._is_pipe

    def get_complete_name_spec(self) -> str:
        return self.name

    def get_connected_node(self, node_id: int) -> _FakeNode:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        return self.nodes[node_id]

    def get_property(self, name: str) -> _FakeProp:
        if name not in self.properties:
            raise KeyError(name)
        return self.properties[name]

    def set_disused(self, value: bool) -> None:
        self.disused = value

    def __repr__(self) -> str:
        return f"_FakeComponent({self.name!r})"


def _link(node: _FakeNode, *components: _FakeComponent) -> None:
    node.connected_components = list(components)


class _FakeModel:
    def __init__(self) -> None:
        self._components: dict[str, _FakeComponent] = {}
        self._nodes: dict[str, object] = {}
        self._signal_lines: dict[str, object] = {}
        self._properties: dict[str, _FakeProp] = {}
        self._route: tuple[list[_FakeComponent], list[int]] | None = None
        self._route_error: Exception | None = None

    # -- general properties --------------------------------------------------
    def get_property(self, name: str) -> _FakeProp:
        if name not in self._properties:
            raise KeyError(name)
        return self._properties[name]

    # -- components ------------------------------------------------------------
    def component_exists(self, name: str) -> bool:
        return name in self._components

    def get_component(self, name: str) -> _FakeComponent:
        return self._components[name]

    def get_all_pipes(self) -> list[_FakeComponent]:
        return [c for c in self._components.values() if c.is_pipe()]

    def get_all_components(self) -> list[_FakeComponent]:
        return list(self._components.values())

    def get_components_name_with_keyword(self, keyword: str) -> list[str]:
        return [name for name in self._components if keyword in name]

    # -- nodes -------------------------------------------------------------------
    def node_exists(self, name: str) -> bool:
        return name in self._nodes

    def get_node(self, name: str):
        return self._nodes[name]

    def get_node_names_with_keyword(self, keyword: str) -> list[str]:
        return [name for name in self._nodes if keyword in name]

    # -- signal lines --------------------------------------------------------------
    def sig_line_exists(self, name: str) -> bool:
        return name in self._signal_lines

    def get_signal_line(self, name: str):
        return self._signal_lines[name]

    def get_signal_line_names_with_keyword(self, keyword: str) -> list[str]:
        return [name for name in self._signal_lines if keyword in name]

    # -- routes ----------------------------------------------------------------------
    def get_route(self, route_id: str):
        if self._route_error is not None:
            raise self._route_error
        if self._route is None:
            raise RuntimeError(f"no route configured for {route_id!r}")
        return self._route


class TestUnitConversion(unittest.TestCase):
    def test_to_model_units_divides_by_factor(self) -> None:
        prop = _FakeProp(unit_factor=2.0)

        self.assertEqual(to_model_units(10.0, prop), 5.0)

    def test_to_model_units_returns_unchanged_for_zero_factor(self) -> None:
        prop = _FakeProp(unit_factor=0.0)

        self.assertEqual(to_model_units(10.0, prop), 10.0)

    def test_to_model_units_returns_unchanged_for_negative_factor(self) -> None:
        prop = _FakeProp(unit_factor=-1.0)

        self.assertEqual(to_model_units(10.0, prop), 10.0)

    def test_to_si_units_multiplies_by_factor(self) -> None:
        prop = _FakeProp(unit_factor=2.0)

        self.assertEqual(to_si_units(5.0, prop), 10.0)


class TestResolveItems(unittest.TestCase):
    def test_empty_identifier_returns_empty_list(self) -> None:
        model = _FakeModel()

        self.assertEqual(resolve_items(model, "   "), [])

    def test_pall_bulk_selector_returns_all_pipes(self) -> None:
        model = _FakeModel()
        model._components["PIPE P1"] = _FakeComponent("PIPE P1", is_pipe=True)
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)

        result = resolve_items(model, "pall")

        self.assertEqual(result, [WandaItemRef("PIPE P1", "component")])

    def test_call_bulk_selector_returns_all_components(self) -> None:
        model = _FakeModel()
        model._components["PIPE P1"] = _FakeComponent("PIPE P1", is_pipe=True)
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)

        result = resolve_items(model, "CALL")

        self.assertEqual({ref.name for ref in result}, {"PIPE P1", "PUMP P1"})

    def test_exact_component_match(self) -> None:
        model = _FakeModel()
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)

        result = resolve_items(model, "PUMP P1")

        self.assertEqual(result, [WandaItemRef("PUMP P1", "component")])

    def test_node_match_by_prefix(self) -> None:
        model = _FakeModel()
        model._nodes["H-node G"] = _FakeNode("H-node G")

        result = resolve_items(model, "H-node G")

        self.assertEqual(result, [WandaItemRef("H-node G", "node")])

    def test_signal_line_match_by_prefix(self) -> None:
        model = _FakeModel()
        model._signal_lines["Signal A.c"] = _FakeNode("Signal A.c")

        result = resolve_items(model, "Signal A.c")

        self.assertEqual(result, [WandaItemRef("Signal A.c", "signal_line")])

    def test_unknown_identifier_falls_back_to_keyword_search(self) -> None:
        model = _FakeModel()
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)
        model._components["PUMP P2"] = _FakeComponent("PUMP P2", is_pipe=False)

        result = resolve_items(model, "PUMP")

        self.assertEqual(sorted(ref.name for ref in result), ["PUMP P1", "PUMP P2"])


class TestApplyParameterChange(unittest.TestCase):
    def test_general_property_set(self) -> None:
        model = _FakeModel()
        model._properties["Time step"] = _FakeProp()
        change = ModelParameterChange(component="general", property="Time step", value=15.0)

        apply_parameter_change(model, change)

        self.assertEqual(model._properties["Time step"].scalar, 15.0)

    def test_disuse_sets_flag_on_matched_component(self) -> None:
        model = _FakeModel()
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)
        change = ModelParameterChange(component="PUMP P1", property="disuse", value=0)

        apply_parameter_change(model, change)

        self.assertTrue(model._components["PUMP P1"].disused)

    def test_property_change_converts_to_model_units(self) -> None:
        model = _FakeModel()
        comp = _FakeComponent("PIPE P1", is_pipe=True)
        comp.properties["Diameter"] = _FakeProp(unit_factor=1000.0)
        model._components["PIPE P1"] = comp
        change = ModelParameterChange(component="PIPE P1", property="Diameter", value=1.0)

        apply_parameter_change(model, change)

        self.assertEqual(comp.properties["Diameter"].scalar, 0.001)

    def test_unknown_component_raises_parameter_application_error(self) -> None:
        model = _FakeModel()
        change = ModelParameterChange(component="MISSING", property="Head", value=1.0)

        with self.assertRaises(ParameterApplicationError) as ctx:
            apply_parameter_change(model, change)

        self.assertIn("MISSING", str(ctx.exception))

    def test_property_error_is_wrapped_as_parameter_application_error(self) -> None:
        model = _FakeModel()
        model._components["PIPE P1"] = _FakeComponent("PIPE P1", is_pipe=True)
        change = ModelParameterChange(component="PIPE P1", property="DoesNotExist", value=1.0)

        with self.assertRaises(ParameterApplicationError) as ctx:
            apply_parameter_change(model, change)

        self.assertIn("PIPE P1.DoesNotExist", str(ctx.exception))


class TestResolveRoutePipes(unittest.TestCase):
    def _build_two_pipe_route(self) -> tuple[_FakeModel, _FakeComponent, _FakeComponent]:
        model = _FakeModel()
        pipe1 = _FakeComponent("PIPE P1", is_pipe=True)
        pipe2 = _FakeComponent("PIPE P2", is_pipe=True)

        node_start = _FakeNode("N-start")
        node_mid = _FakeNode("N-mid")
        node_end = _FakeNode("N-end")

        pipe1.nodes = {1: node_start, 2: node_mid}
        pipe2.nodes = {1: node_mid, 2: node_end}

        _link(node_start, pipe1)
        _link(node_mid, pipe1, pipe2)
        _link(node_end, pipe2)

        model._components["PIPE P1"] = pipe1
        model._components["PIPE P2"] = pipe2
        return model, pipe1, pipe2

    def test_empty_route_id_returns_empty_list(self) -> None:
        model = _FakeModel()

        self.assertEqual(resolve_route_pipes(model, "   "), [])

    def test_forward_route_via_get_route(self) -> None:
        model, pipe1, pipe2 = self._build_two_pipe_route()
        model._route = ([pipe1, pipe2], [1, 1])

        result = resolve_route_pipes(model, "Route A")

        self.assertEqual(result, [("PIPE P1", 1), ("PIPE P2", 1)])

    def test_reversed_route_is_normalized(self) -> None:
        model, pipe1, pipe2 = self._build_two_pipe_route()
        model._route = ([pipe1, pipe2], [-1, -1])

        result = resolve_route_pipes(model, "Route A")

        self.assertEqual(result, [("PIPE P2", 1), ("PIPE P1", 1)])

    def test_get_route_failure_falls_back_to_single_item_resolution(self) -> None:
        model = _FakeModel()
        model._route_error = RuntimeError("no such route")
        model._components["PIPE P1"] = _FakeComponent("PIPE P1", is_pipe=True)

        result = resolve_route_pipes(model, "PIPE P1")

        self.assertEqual(result, [("PIPE P1", 1)])

    def test_get_route_failure_with_non_pipe_single_item_returns_empty(self) -> None:
        model = _FakeModel()
        model._route_error = RuntimeError("no such route")
        model._components["PUMP P1"] = _FakeComponent("PUMP P1", is_pipe=False)

        result = resolve_route_pipes(model, "PUMP P1")

        self.assertEqual(result, [])


class TestFindItemsWithKeyword(unittest.TestCase):
    def test_empty_keyword_returns_empty_list(self) -> None:
        model = _FakeModel()

        self.assertEqual(find_items_with_keyword(model, "   "), [])


class TestGetConnectedNodes(unittest.TestCase):
    def test_returns_all_nine_nodes_when_all_present(self) -> None:
        component = _FakeComponent("PIPE P1", is_pipe=True)
        for node_id in range(1, 10):
            component.nodes[node_id] = _FakeNode(f"N{node_id}")

        connected = _get_connected_nodes(component)

        self.assertEqual(set(connected), set(range(1, 10)))

    def test_stops_at_first_missing_node(self) -> None:
        component = _FakeComponent("PIPE P1", is_pipe=True)
        component.nodes[1] = _FakeNode("N1")

        connected = _get_connected_nodes(component)

        self.assertEqual(set(connected), {1})


class _ExplodingNode:
    def get_connected_components(self):
        raise RuntimeError("boom")


class TestGetConnectedComponents(unittest.TestCase):
    def test_node_with_failing_get_connected_components_is_skipped(self) -> None:
        component = _FakeComponent("PIPE P1", is_pipe=True)
        connected_nodes = {1: _ExplodingNode()}

        result = _get_connected_components(component, connected_nodes)

        self.assertEqual(result, {})

    def test_allowed_filter_excludes_disallowed_components(self) -> None:
        component = _FakeComponent("PIPE P1", is_pipe=True)
        other = _FakeComponent("PIPE P2", is_pipe=True)
        excluded = _FakeComponent("PIPE P3", is_pipe=True)
        node = _FakeNode("N-mid")
        _link(node, other, excluded)

        result = _get_connected_components(component, {1: node}, allowed={component, other})

        self.assertEqual(set(result), {other})


class TestFindRoute(unittest.TestCase):
    def test_returns_none_when_no_route_exists(self) -> None:
        comp_a = _FakeComponent("A")
        comp_b = _FakeComponent("B")
        graph = {comp_a: {}, comp_b: {}}  # type: ignore[var-annotated]

        result = _find_route(graph, comp_a, comp_b)

        self.assertIsNone(result)


class TestConnectionNodeId(unittest.TestCase):
    def test_returns_none_when_no_connection_found(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        node = _FakeNode("N1")
        _link(node, comp_a)
        comp_a.nodes[1] = node

        self.assertIsNone(_connection_node_id(comp_a, comp_b))

    def test_skips_nodes_whose_get_connected_components_fails(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        comp_a.nodes[1] = _ExplodingNode()  # type: ignore[assignment]
        good_node = _FakeNode("N2")
        _link(good_node, comp_a, comp_b)
        comp_a.nodes[2] = good_node

        self.assertEqual(_connection_node_id(comp_a, comp_b), 2)

    def test_returns_node_id_for_matching_neighbour(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        node = _FakeNode("N1")
        _link(node, comp_a, comp_b)
        comp_a.nodes[1] = node

        self.assertEqual(_connection_node_id(comp_a, comp_b), 1)


class TestPipeDirectionFromRouteComponentIndex(unittest.TestCase):
    def test_single_component_route_defaults_to_reverse(self) -> None:
        comp = _FakeComponent("A", is_pipe=True)

        self.assertEqual(_pipe_direction_from_route_component_index([comp], 0), 1)

    def test_node_id_one_means_reverse_direction(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        node = _FakeNode("N1")
        _link(node, comp_a, comp_b)
        comp_a.nodes[1] = node

        direction = _pipe_direction_from_route_component_index([comp_a, comp_b], 0)

        self.assertEqual(direction, -1)

    def test_unmatched_neighbour_defaults_to_forward(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        # comp_a has no connections at all, so _connection_node_id returns None.

        direction = _pipe_direction_from_route_component_index([comp_a, comp_b], 0)

        self.assertEqual(direction, 1)

    def test_last_component_uses_previous_neighbour(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        node = _FakeNode("N2")
        _link(node, comp_a, comp_b)
        comp_b.nodes[2] = node

        direction = _pipe_direction_from_route_component_index([comp_a, comp_b], 1)

        self.assertEqual(direction, 1)


class TestOrderComponentsByConnection(unittest.TestCase):
    def test_single_component_returned_unchanged(self) -> None:
        comp = _FakeComponent("A", is_pipe=True)

        self.assertEqual(_order_components_by_connection([comp]), [comp])

    def test_empty_graph_returns_components_unchanged(self) -> None:
        # No components -> _build_component_graph returns {} -> falsy.
        self.assertEqual(_order_components_by_connection([]), [])

    def test_no_route_found_returns_components_unchanged(self) -> None:
        # Two disconnected components: graph has entries but no path between them.
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        # Both have no connected nodes -> both treated as endpoints with 0 neighbours.

        with self.assertLogs("pywandahydra.wanda.api", level="WARNING") as cm:
            result = _order_components_by_connection([comp_a, comp_b])

        self.assertEqual(result, [comp_a, comp_b])
        self.assertTrue(any("No connected path" in msg for msg in cm.output))

    def test_route_shorter_than_components_appends_missing(self) -> None:
        comp_a = _FakeComponent("A", is_pipe=True)
        comp_b = _FakeComponent("B", is_pipe=True)
        comp_c = _FakeComponent("C", is_pipe=True)
        node = _FakeNode("N1")
        _link(node, comp_a, comp_b)
        comp_a.nodes[1] = node
        comp_b.nodes[1] = node
        # comp_c is isolated, not connected to anything.

        result = _order_components_by_connection([comp_a, comp_b, comp_c])

        self.assertIn(comp_c, result)
        self.assertEqual(len(result), 3)


class TestNormalizePipeRouteOrientation(unittest.TestCase):
    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(_normalize_pipe_route_orientation([]), [])


class TestPipeName(unittest.TestCase):
    def test_falls_back_to_str_when_no_complete_name_spec(self) -> None:
        self.assertEqual(_pipe_name("PIPE-X"), "PIPE-X")

    def test_uses_complete_name_spec_when_available(self) -> None:
        comp = _FakeComponent("PIPE P1", is_pipe=True)

        self.assertEqual(_pipe_name(comp), "PIPE P1")


class TestResolveRoutePipesFallback(unittest.TestCase):
    def test_get_route_failure_with_multiple_items_orders_and_resolves(self) -> None:
        model = _FakeModel()
        model._route_error = RuntimeError("no such route")
        pipe1 = _FakeComponent("PIPE P1", is_pipe=True)
        pipe2 = _FakeComponent("PIPE P2", is_pipe=True)
        node_mid = _FakeNode("N-mid")
        _link(node_mid, pipe1, pipe2)
        pipe1.nodes[2] = node_mid
        pipe2.nodes[1] = node_mid
        model._components["PIPE P1"] = pipe1
        model._components["PIPE P2"] = pipe2

        result = resolve_route_pipes(model, "PIPE")

        self.assertEqual({name for name, _ in result}, {"PIPE P1", "PIPE P2"})

    def test_get_route_failure_with_no_resolved_items_returns_empty(self) -> None:
        model = _FakeModel()
        model._route_error = RuntimeError("no such route")

        result = resolve_route_pipes(model, "NOTHING")

        self.assertEqual(result, [])

    def test_get_route_with_zero_direction_is_inferred(self) -> None:
        model, pipe1, pipe2 = self._build_two_pipe_route()
        model._route = ([pipe1, pipe2], [0, 0])

        result = resolve_route_pipes(model, "Route A")

        self.assertEqual({name for name, _ in result}, {"PIPE P1", "PIPE P2"})

    def test_get_route_with_non_pipe_component_is_skipped_for_direction(self) -> None:
        model, pipe1, pipe2 = self._build_two_pipe_route()
        pump = _FakeComponent("PUMP P1", is_pipe=False)
        model._route = ([pipe1, pump, pipe2], [1, 1, 1])

        result = resolve_route_pipes(model, "Route A")

        self.assertEqual({name for name, _ in result}, {"PIPE P1", "PIPE P2"})

    def test_fallback_skips_item_refs_that_fail_to_resolve(self) -> None:
        model = _FakeModel()
        model._route_error = RuntimeError("no such route")
        model._components["PUMP"] = _FakeComponent("PUMP", is_pipe=False)
        model._components["PUMP1"] = _FakeComponent("PUMP1", is_pipe=False)

        # Patch get_item (via api module) is unnecessary: use a component whose
        # get_complete_name_spec raises during get_item resolution is hard with
        # _FakeModel's get_component, so instead construct a ref pointing to a
        # missing component to trigger the exception path in get_item.
        bad_ref = WandaItemRef("MISSING", "component")
        with self.assertRaises(KeyError):
            model.get_component("MISSING")

        # Directly exercise resolve_route_pipes fallback with a mix of
        # resolvable and unresolvable refs by monkeypatching resolve_items.
        import pywandahydra.wanda.api as api_module

        original_resolve_items = api_module.resolve_items
        try:
            api_module.resolve_items = lambda _model, _identifier: [
                bad_ref,
                WandaItemRef("PUMP", "component"),
            ]
            result = resolve_route_pipes(model, "PUMP")
        finally:
            api_module.resolve_items = original_resolve_items

        self.assertEqual(result, [])

    def _build_two_pipe_route(self) -> tuple[_FakeModel, _FakeComponent, _FakeComponent]:
        model = _FakeModel()
        pipe1 = _FakeComponent("PIPE P1", is_pipe=True)
        pipe2 = _FakeComponent("PIPE P2", is_pipe=True)

        node_start = _FakeNode("N-start")
        node_mid = _FakeNode("N-mid")
        node_end = _FakeNode("N-end")

        pipe1.nodes = {1: node_start, 2: node_mid}
        pipe2.nodes = {1: node_mid, 2: node_end}

        _link(node_start, pipe1)
        _link(node_mid, pipe1, pipe2)
        _link(node_end, pipe2)

        model._components["PIPE P1"] = pipe1
        model._components["PIPE P2"] = pipe2
        return model, pipe1, pipe2


if __name__ == "__main__":
    unittest.main()

