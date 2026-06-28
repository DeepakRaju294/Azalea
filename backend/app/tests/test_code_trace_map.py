"""Deterministic trace->code-line mapper (code_trace_map.py): identifier overlap for operation prose,
AST loop-body fallback for state-dump prose. No LLM, no hardcoded code. Fully offline."""
import unittest

from app.services.examples.code_trace_map import (code_block_for_step, looks_negative,
                                                  main_loop_span, map_work_lines_to_code)

_KRUSKAL = """class DisjointSet:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, u):
        if self.parent[u] != u:
            self.parent[u] = self.find(self.parent[u])
        return self.parent[u]

    def union(self, u, v):
        self.parent[self.find(u)] = self.find(v)

def kruskal(n, edges):
    edges.sort(key=lambda x: x[2])
    ds = DisjointSet(n)
    mst = []
    for u, v, weight in edges:
        if ds.find(u) != ds.find(v):
            ds.union(u, v)
            mst.append((u, v, weight))
    return mst
"""  # line 17 = `for`; body[0] = `if` on 18; union = 19; append = 20; `return` = 21


class TokenOverlapTests(unittest.TestCase):
    def test_operation_prose_maps_to_named_lines(self):
        # work prose that NAMES the operations lands on the matching code lines.
        work = ["call ds.union to merge the components", "append the edge to mst"]
        out = map_work_lines_to_code(_KRUSKAL, work)
        self.assertIsNotNone(out)
        self.assertEqual(len(out), len(work))
        self.assertEqual(out[0], [19])   # the ds.union(u, v) line
        self.assertEqual(out[1], [20])   # the mst.append line

    def test_no_overlap_returns_none(self):
        self.assertIsNone(map_work_lines_to_code(_KRUSKAL, ["selected_edges: []", "components: [[A]]"]))

    def test_empty_inputs(self):
        self.assertIsNone(map_work_lines_to_code("", ["x"]))
        self.assertIsNone(map_work_lines_to_code(_KRUSKAL, []))


class StructuralFallbackTests(unittest.TestCase):
    def test_main_loop_span_finds_the_for_loop(self):
        body_start, body_end, guard = main_loop_span(_KRUSKAL)
        self.assertEqual(body_start, 18)   # body[0] = the `if` test
        self.assertEqual(body_end, 20)     # the mst.append line
        self.assertEqual(guard, 18)        # the `if ds.find(u) != ds.find(v)` test

    def test_accept_step_highlights_full_body_skip_highlights_guard(self):
        self.assertEqual(code_block_for_step(_KRUSKAL, negative=False), [18, 20])  # accept
        self.assertEqual(code_block_for_step(_KRUSKAL, negative=True), [18, 18])   # skip → guard only

    def test_looks_negative(self):
        self.assertTrue(looks_negative("Edge (C,D,5) skip; MST so far ..."))
        self.assertTrue(looks_negative("already connected, forms a cycle"))
        self.assertFalse(looks_negative("Edge (A,B,2) accept; MST so far ..."))

    def test_unparseable_code_returns_none(self):
        self.assertIsNone(main_loop_span("def f(:\n  pass"))
        self.assertIsNone(code_block_for_step("not python {{{", negative=False))


if __name__ == "__main__":
    unittest.main()
