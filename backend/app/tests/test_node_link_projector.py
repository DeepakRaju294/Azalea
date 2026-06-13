"""project_node_link across a graph-algorithm FAMILY (PROJECTOR_SYSTEM_SPEC §4, §15 test 2).

BFS, DFS, Prim, and Dijkstra are each traced → projected → folded → compiled by ONE
projector with no per-algorithm branch. We assert the resulting node/edge highlight
sequences are correct — the proof the reader is graph-generic, not topic-specific.

Run: python -m unittest app.tests.test_node_link_projector
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.compilers import node_link as node_link_compiler
from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.projectors.node_link import (
    GraphProjection,
    project_node_link,
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

DFS_CODE = '''
def dfs(graph, start):
    visited = []
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.append(node)
        for nb in reversed(graph[node]):
            if nb not in visited:
                stack.append(nb)
    return visited
'''

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

DIJKSTRA_CODE = '''
def dijkstra(nodes, edges, start):
    import heapq
    dist = {n: 999 for n in nodes}
    dist[start] = 0
    done = []
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.append(u)
        for edge in edges:
            a, b, w = edge
            if a == u or b == u:
                v = b if a == u else a
                if d + w < dist[v]:
                    dist[v] = d + w
                    heapq.heappush(pq, (dist[v], v))
    return done
'''

_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}
_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W_EDGES = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]
_BASE = {"nodes": _NODES, "edges": _EDGES}


def _compile(code, entry, input_spec, projection, start):
    steps, _ = trace_execution(code, entry, input_spec)
    assert validate_projection(steps, _BASE, projection) == [], validate_projection(steps, _BASE, projection)
    result = project_node_link(steps, _BASE, projection)
    frames = DeltaFoldEngine().fold(
        result.initial_state(start), result.deltas, set(_NODES), delta_vocabulary("graph_network")
    )
    model, _ = node_link_compiler.compile_from_trace(
        trace={"steps": result.deltas},
        frames=frames,
        base_structure=_BASE,
        profile=profile_for_mode("graph_network"),
        mode="graph_network",
        model_id="t",
    )
    return result, model


def _final_nodes(model):
    state = model["frames"][-1]["state"]
    nodes = {e["node_id"] for e in state["node_state_map"] if e["state"] in ("completed", "current", "newly_discovered")}
    if state.get("active_node"):
        nodes.add(state["active_node"])
    return nodes


def _final_edges(model):
    state = model["frames"][-1]["state"]
    return list(zip(state.get("completed_edges_from") or [], state.get("completed_edges_to") or []))


class TestTraversalFamily(unittest.TestCase):
    def test_bfs_visits_every_node(self):
        proj = GraphProjection(current_from="node", visit_order_from="visited", frontier_from="queue")
        result, model = _compile(BFS_CODE, "bfs", {"args": [_GRAPH, "A"]}, proj, "A")
        self.assertGreaterEqual(result.emitted_step_count, len(_NODES))   # ~one step per visit
        self.assertEqual(_final_nodes(model), set(_NODES))                # all reached
        self.assertEqual(len({d["event_id"] for d in result.deltas}), len(result.deltas))  # unique ids

    def test_dfs_visits_every_node(self):
        proj = GraphProjection(current_from="node", visit_order_from="visited", frontier_from="stack")
        _result, model = _compile(DFS_CODE, "dfs", {"args": [_GRAPH, "A"]}, proj, "A")
        self.assertEqual(_final_nodes(model), set(_NODES))

    def test_dijkstra_uses_priority_queue_node_key(self):
        # pq holds (dist, node) tuples → frontier_node_key="index:1".
        proj = GraphProjection(
            current_from="u", visit_order_from="done", frontier_from="pq", frontier_node_key="index:1"
        )
        _result, model = _compile(DIJKSTRA_CODE, "dijkstra", {"args": [_NODES, _W_EDGES, "A"]}, proj, "A")
        self.assertEqual(_final_nodes(model), set(_NODES))


class TestEdgeSelectionFamily(unittest.TestCase):
    def test_prim_selects_v_minus_1_real_edges(self):
        proj = GraphProjection(current_from="node", visited_from="in_mst", selected_edges_from="mst")
        result, model = _compile(PRIM_CODE, "prim", {"args": [_NODES, _W_EDGES, "A"]}, proj, "A")
        edges = _final_edges(model)
        self.assertEqual(len(edges), len(_NODES) - 1)                      # MST has |V|-1 edges
        real = {frozenset((a, b)) for a, b in _EDGES}
        for a, b in edges:
            self.assertIn(frozenset((a, b)), real)                        # every selected edge is real
        # the projector emitted commit_edge events
        self.assertTrue(any(d["step_role"] == "commit_edge" for d in result.deltas))

    def test_prim_active_edge_tracks_each_selection(self):
        proj = GraphProjection(current_from="node", visited_from="in_mst", selected_edges_from="mst")
        _result, model = _compile(PRIM_CODE, "prim", {"args": [_NODES, _W_EDGES, "A"]}, proj, "A")
        # every commit frame names a real active edge
        for frame in model["frames"]:
            af, at = frame["state"].get("active_edge_from"), frame["state"].get("active_edge_to")
            if af and at:
                self.assertIn(frozenset((af, at)), {frozenset((a, b)) for a, b in _EDGES})


if __name__ == "__main__":
    unittest.main()
