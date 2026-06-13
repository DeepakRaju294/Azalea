"""infer_projection over a 5-algorithm family (PROJECTOR_SYSTEM_SPEC §8, §15 test 4).

BFS, DFS, Dijkstra, Prim, Kruskal — one inference recovers a VALID GraphProjection for
each, with no per-algorithm branch (asserted by reading the source). T3 = zero
hand-authored artifacts.

Run: python -m unittest app.tests.test_projection_inference
"""
from __future__ import annotations

import os
import pathlib
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.projectors import node_link as NL
from app.services.visual_v2.projectors.node_link import (
    infer_projection,
    project_node_link,
    validate_projection,
)
from app.services.visual_v2.simulators.code_tracer import trace_execution

_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]
_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}
_BASE = {"nodes": _NODES, "edges": _EDGES}

BFS = ('''
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
''', "bfs", {"args": [_GRAPH, "A"]})

DFS = ('''
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
''', "dfs", {"args": [_GRAPH, "A"]})

DIJKSTRA = ('''
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
''', "dijkstra", {"args": [_NODES, _W, "A"]})

PRIM = ('''
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
''', "prim", {"args": [_NODES, _W, "A"]})

KRUSKAL = ('''
def kruskal(nodes, edges, start):
    parent = {n: n for n in nodes}
    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    mst = []
    visited = []
    for edge in sorted(edges, key=lambda e: e[2]):
        a, b, w = edge
        if find(a) != find(b):
            parent[find(a)] = find(b)
            mst.append((a, b))
            if a not in visited:
                visited.append(a)
            if b not in visited:
                visited.append(b)
    return mst
''', "kruskal", {"args": [_NODES, _W, "A"]})

_FAMILY = {"bfs": BFS, "dfs": DFS, "dijkstra": DIJKSTRA, "prim": PRIM, "kruskal": KRUSKAL}


class TestInferenceFamily(unittest.TestCase):
    def test_infers_valid_contract_for_every_algorithm(self):
        for name, (code, entry, inp) in _FAMILY.items():
            steps, _ = trace_execution(code, entry, inp)
            cand = infer_projection(steps, _BASE)
            self.assertIsNotNone(cand, f"{name}: inference returned None")
            # the inferred contract VALIDATES against the same trace
            self.assertEqual(validate_projection(steps, _BASE, cand.projection), [], f"{name}: {cand.projection}")
            # and produces a non-empty, changing projection
            result = project_node_link(steps, _BASE, cand.projection, projection_source="inferred")
            self.assertGreaterEqual(result.emitted_step_count, 1, name)
            self.assertIn(cand.confidence_band, ("high", "medium", "low"))

    def test_inference_finds_visited_or_order(self):
        steps, _ = trace_execution(*BFS[:2], BFS[2])
        cand = infer_projection(steps, _BASE)
        self.assertTrue(cand.projection.visited_from or cand.projection.visit_order_from)

    def test_prim_infers_selected_edges(self):
        steps, _ = trace_execution(*PRIM[:2], PRIM[2])
        cand = infer_projection(steps, _BASE)
        self.assertIsNotNone(cand.projection.selected_edges_from)


class TestNoApplicationBranch(unittest.TestCase):
    def test_projector_source_has_no_application_name_branch(self):
        # §8 / §18 rule 8 — shape code may not branch on the application/algorithm name.
        src = pathlib.Path(NL.__file__).read_text(encoding="utf-8").lower()
        for forbidden in ("application ==", "application==", 'algorithm ==', "== \"bfs\"", "== 'prim'"):
            self.assertNotIn(forbidden, src, f"projector branches on a name: {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
