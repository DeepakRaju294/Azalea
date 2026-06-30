"""A2 (STUDY_PATH_CONTENT_SPEC §A2) — executable validation of a displayed coding implementation.
Pure MST property checker + runnable detection + real subprocess execution on correct vs broken code.
Fully offline (no LLM); the subprocess runs the venv python on a temp harness."""
import unittest

from app.services.examples.code_execution_check import (check_graph_topic_code, find_entry_function,
                                                        is_runnable, mst_properties,
                                                        validate_graph_implementation)

# A 4-node graph (A,B,C,D); a minimum spanning tree has weight 1+1+2 = 4.
_NODES = 4
_EDGES = [["A", "B", 1], ["B", "C", 1], ["B", "D", 2], ["A", "C", 3], ["C", "D", 5]]
_ADJ = {"A": [["B", 1], ["C", 3]], "B": [["A", 1], ["C", 1], ["D", 2]],
        "C": [["A", 3], ["B", 1], ["D", 5]], "D": [["B", 2], ["C", 5]]}
_MIN_TOTAL = 4

_KRUSKAL_OK = """
class DisjointSet:
    def __init__(self, n):
        self.parent = list(range(n))
    def find(self, u):
        while self.parent[u] != u:
            self.parent[u] = self.parent[self.parent[u]]; u = self.parent[u]
        return u
    def union(self, u, v):
        self.parent[self.find(u)] = self.find(v)

def kruskal(n, edges):
    edges.sort(key=lambda e: e[2])
    ds = DisjointSet(n)
    mst = []
    for u, v, w in edges:
        if ds.find(u) != ds.find(v):
            ds.union(u, v)
            mst.append([u, v, w])
    return mst
"""

# The live bug: returns VERTICES, not edges.
_PRIM_VERTICES = """
import heapq
def prim(graph):
    start = next(iter(graph))
    visited = set()
    heap = [(0, start, None)]
    mst_edges = []
    total = 0
    while heap:
        w, u, _p = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u); total += w
        if w > 0:
            mst_edges.append(u)
        for v, weight in graph[u]:
            if v not in visited:
                heapq.heappush(heap, (weight, v, u))
    return mst_edges, total
"""


class PureMstChecker(unittest.TestCase):
    def test_valid_mst_passes(self):
        tree = [["A", "B", 1], ["B", "C", 1], ["B", "D", 2]]
        self.assertTrue(mst_properties(_NODES, _EDGES, tree, _MIN_TOTAL).ok)

    def test_vertices_not_edges_fail(self):
        r = mst_properties(_NODES, _EDGES, (["B", "C", "D"], 4), _MIN_TOTAL)
        self.assertEqual(r.status, "fail")          # ['B','C','D'] are not edge triples

    def test_wrong_edge_count_fails(self):
        self.assertEqual(mst_properties(_NODES, _EDGES, [["A", "B", 1]], _MIN_TOTAL).status, "fail")

    def test_cycle_fails(self):
        cyc = [["A", "B", 1], ["B", "C", 1], ["A", "C", 3]]   # 3 edges among A,B,C -> cycle, D missing
        self.assertEqual(mst_properties(_NODES, _EDGES, cyc, _MIN_TOTAL).status, "fail")

    def test_non_minimal_total_fails(self):
        tree = [["A", "B", 1], ["A", "C", 3], ["B", "D", 2]]   # spanning but weight 6 != 4
        r = mst_properties(_NODES, _EDGES, tree, _MIN_TOTAL)
        self.assertEqual(r.status, "fail")

    def test_edge_not_in_graph_fails(self):
        tree = [["A", "B", 1], ["B", "C", 1], ["A", "D", 9]]   # A-D(9) not a graph edge
        self.assertEqual(mst_properties(_NODES, _EDGES, tree, _MIN_TOTAL).status, "fail")


class RunnableDetection(unittest.TestCase):
    def test_full_program_is_runnable(self):
        self.assertTrue(is_runnable(_KRUSKAL_OK))
        self.assertEqual(find_entry_function(_KRUSKAL_OK, "kruskal"), "kruskal")

    def test_snippet_is_not_runnable(self):
        self.assertFalse(is_runnable("    mst.append((u, v, w))  # fragment"))

    def test_third_party_dep_not_runnable(self):
        self.assertFalse(is_runnable("import networkx as nx\ndef f(g):\n    return nx.mst(g)"))


class EndToEndExecution(unittest.TestCase):
    def test_correct_kruskal_passes(self):
        r = validate_graph_implementation(_KRUSKAL_OK, num_nodes=_NODES, edges=_EDGES, adjacency=_ADJ,
                                          expected_total=_MIN_TOTAL, slug="kruskal")
        self.assertEqual(r.status, "ok", r.reason)

    def test_prim_returning_vertices_fails(self):
        r = validate_graph_implementation(_PRIM_VERTICES, num_nodes=_NODES, edges=_EDGES, adjacency=_ADJ,
                                          expected_total=_MIN_TOTAL, slug="prim")
        self.assertEqual(r.status, "fail", r.reason)   # the live A2 bug is caught by execution


class SelfContainedTopicCheck(unittest.TestCase):
    """The wired entry: generate test graphs internally, compute the true MST total, run the code."""
    def test_correct_kruskal_passes_on_generated_graphs(self):
        self.assertEqual(check_graph_topic_code(_KRUSKAL_OK, "kruskal").status, "ok")

    def test_prim_returning_vertices_fails_on_generated_graphs(self):
        self.assertEqual(check_graph_topic_code(_PRIM_VERTICES, "prim").status, "fail")

    def test_prim_with_start_vertex_validates(self):
        # A2 now handles the (graph, start) signature (Prim/BFS/DFS) rather than returning unverifiable.
        code = """
import heapq
def prim(graph, start):
    visited = {start}
    edges = []
    pq = [(w, start, v) for v, w in graph[start]]
    heapq.heapify(pq)
    while pq:
        w, u, v = heapq.heappop(pq)
        if v in visited:
            continue
        visited.add(v)
        edges.append([u, v, w])
        for nv, nw in graph[v]:
            if nv not in visited:
                heapq.heappush(pq, (nw, v, nv))
    return edges
"""
        self.assertEqual(check_graph_topic_code(code, "prim").status, "ok")

    def test_non_graph_topic_is_unverifiable(self):
        self.assertEqual(check_graph_topic_code(_KRUSKAL_OK, "binary_search").status, "unverifiable")


class CodeSwapHelper(unittest.TestCase):
    def test_replace_lesson_code_snippets_swaps_only_code_cards(self):
        from app.services.examples.solver import _replace_lesson_code_snippets
        cards = [{"code_snippet": "old1"}, {"blueprint_key": "background"}, {"code_snippet": "old2"}]
        _replace_lesson_code_snippets(cards, "NEWCODE")
        self.assertEqual(cards[0]["code_snippet"], "NEWCODE")
        self.assertNotIn("code_snippet", cards[1])      # non-code card untouched
        self.assertEqual(cards[2]["code_snippet"], "NEWCODE")


if __name__ == "__main__":
    unittest.main()
