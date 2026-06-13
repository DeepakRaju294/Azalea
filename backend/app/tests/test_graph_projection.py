"""GraphProjection contract + §6.3 projection validator (PROJECTOR_SYSTEM_SPEC §3, §6.3).

The validator is checked against REAL traced code for a *family* (BFS + Prim), proving
it resolves graph state generically with no per-algorithm branch (§15 / §18 rule 8).
Helpers and negative cases are asserted by defect shape, not topic.

Run: python -m unittest app.tests.test_graph_projection
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.projectors.node_link import (
    GraphProjection,
    apply_node_key,
    normalize_edge,
    validate_projection,
)
from app.services.visual_v2.simulators.code_tracer import trace_execution

BFS_CODE = '''
def bfs(graph, start):
    visited = []
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.append(node)
        for nb in graph[node]:
            if nb not in visited:
                queue.append(nb)
    return visited
'''

# Prim's MST: a DIFFERENT algorithm/shape of state (selected edges + in_mst set),
# read by the SAME validator with no algorithm-specific code.
PRIM_CODE = '''
def prim(nodes, edges, start):
    in_mst = [start]
    mst = []
    while len(in_mst) < len(nodes):
        best = None
        for edge in edges:
            a, b, w = edge
            if (a in in_mst) != (b in in_mst):
                if best is None or w < best[2]:
                    best = (a, b, w)
        a, b, w = best
        node = b if a in in_mst else a
        in_mst.append(node)
        mst.append((a, b))
    return mst
'''

_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}
_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W_EDGES = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]


def _bfs_steps():
    steps, _ = trace_execution(BFS_CODE, "bfs", {"args": [_GRAPH, "A"]})
    return steps


def _prim_steps():
    steps, _ = trace_execution(PRIM_CODE, "prim", {"args": [_NODES, _W_EDGES, "A"]})
    return steps


class TestNormalizationHelpers(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(apply_node_key("C", "identity"), "C")

    def test_val_on_dict(self):
        self.assertEqual(apply_node_key({"val": 7}, "val"), 7)

    def test_index_key_on_tuple(self):
        self.assertEqual(apply_node_key([3, "C"], "index:1"), "C")  # (priority, node)

    def test_attr_key(self):
        self.assertEqual(apply_node_key({"node": "Z"}, "attr:node"), "Z")

    def test_normalize_edge_identity(self):
        self.assertEqual(normalize_edge(["A", "B"]), ("A", "B"))

    def test_normalize_edge_attr(self):
        self.assertEqual(normalize_edge({"u": "A", "v": "B"}, "attr:u,v"), ("A", "B"))


class TestValidatesRealTraces(unittest.TestCase):
    def test_bfs_projection_validates(self):
        proj = GraphProjection(current_from="node", visit_order_from="visited", frontier_from="queue")
        errs = validate_projection(_bfs_steps(), {"nodes": _NODES, "edges": _EDGES}, proj)
        self.assertEqual(errs, [], errs)

    def test_prim_projection_validates(self):
        # Same validator, different algorithm: visited set + selected edges.
        proj = GraphProjection(
            current_from="node", visited_from="in_mst", selected_edges_from="mst"
        )
        errs = validate_projection(_prim_steps(), {"nodes": _NODES, "edges": _EDGES}, proj)
        self.assertEqual(errs, [], errs)


class TestRejectsBadContracts(unittest.TestCase):
    def test_unknown_variable_rejected(self):
        proj = GraphProjection(current_from="does_not_exist", visit_order_from="visited")
        errs = validate_projection(_bfs_steps(), {"nodes": _NODES, "edges": _EDGES}, proj)
        self.assertTrue(any("never appears in the trace" in e for e in errs), errs)

    def test_missing_visited_rejected(self):
        proj = GraphProjection(current_from="node")  # neither visited_from nor visit_order_from
        errs = validate_projection(_bfs_steps(), {"nodes": _NODES, "edges": _EDGES}, proj)
        self.assertTrue(any("visited_from / visit_order_from is required" in e for e in errs), errs)

    def test_selected_edge_not_in_graph_rejected(self):
        # Prim selects real edges; remove one from base so the contract no longer resolves.
        proj = GraphProjection(current_from="node", visited_from="in_mst", selected_edges_from="mst")
        broken_base = {"nodes": _NODES, "edges": [["A", "B"]]}  # missing most edges
        errs = validate_projection(_prim_steps(), broken_base, proj)
        self.assertTrue(any("not in base_structure.edges" in e for e in errs), errs)

    def test_empty_state_rejected(self):
        # Synthetic trace whose 'current' never names a real node.
        steps = [{"vars": {"node": "Z", "visited": []}} for _ in range(3)]
        proj = GraphProjection(current_from="node", visit_order_from="visited")
        errs = validate_projection(steps, {"nodes": _NODES, "edges": _EDGES}, proj)
        self.assertTrue(any("not a node in base_structure" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
