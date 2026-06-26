"""Reference-first worked-example construction: correct, complete MST cards from a trusted run."""
import unittest

from app.services.gen_foundation.reference_first import (
    build_reference_cards, kruskal_steps, prim_steps, _algorithm_for,
)
from app.services.gen_foundation.property_checks import _node_labels, _weighted_edges, _reference_mst

GRAPH = {"graph": {"nodes": ["A", "B", "C", "D", "E"],
                   "edges": [["A", "B", 6], ["A", "C", 1], ["C", "B", 2], ["B", "D", 5],
                             ["C", "D", 8], ["D", "E", 3], ["C", "E", 7]]}}


class ReferenceFirstTests(unittest.TestCase):
    def setUp(self):
        self.nodes = _node_labels(GRAPH)
        self.edges = _weighted_edges(GRAPH)
        self.ref_w, self.ref_c = _reference_mst(self.nodes, self.edges)

    def _weight(self, mst):
        return sum(w for _u, _v, w in mst)

    def test_kruskal_matches_reference(self):
        _steps, mst = kruskal_steps(self.nodes, self.edges)
        self.assertEqual(len(mst), self.ref_c)
        self.assertAlmostEqual(self._weight(mst), self.ref_w)

    def test_prim_matches_reference(self):
        _steps, mst = prim_steps(self.nodes, self.edges, start="A")
        self.assertEqual(len(mst), self.ref_c)
        self.assertAlmostEqual(self._weight(mst), self.ref_w)

    def test_prim_and_kruskal_same_total(self):
        _s1, m1 = kruskal_steps(self.nodes, self.edges)
        _s2, m2 = prim_steps(self.nodes, self.edges, start="A")
        self.assertAlmostEqual(self._weight(m1), self._weight(m2))

    def test_algorithm_detection(self):
        self.assertEqual(_algorithm_for("Understanding Prim's Algorithm"), "prim")
        self.assertEqual(_algorithm_for("Kruskal's Algorithm for MST"), "kruskal")

    def test_cards_are_correct_and_complete(self):
        for title in ["Kruskal's Algorithm", "Understanding Prim's Algorithm"]:
            r = build_reference_cards("graph_mst", title, GRAPH)
            self.assertTrue(r["cards"])
            self.assertEqual(len(r["final_answer"]), self.ref_c, title)
            self.assertAlmostEqual(self._weight([tuple(e) for e in r["final_answer"]]), self.ref_w, msg=title)
            self.assertEqual(r["source"], "reference_first")
            self.assertTrue(r["trace_backed"])
            # every step card has the liked format fields
            for c in r["cards"]:
                self.assertTrue(c["goal"] and c["work"] and c["result"])
                self.assertTrue(c["trace_backed"])

    def test_problem_states_same_graph(self):
        r = build_reference_cards("graph_mst", "Kruskal's Algorithm", GRAPH)
        self.assertIn("minimum spanning tree", r["problem"].lower())
        for n in ["A", "B", "C", "D", "E"]:
            self.assertIn(n, r["problem"])

    def test_non_mst_family_skipped(self):
        self.assertEqual(build_reference_cards("sorting", "Bubble Sort", GRAPH), {})

    def test_no_edges_skipped(self):
        self.assertEqual(build_reference_cards("graph_mst", "Kruskal", {"nodes": ["A", "B"]}), {})


if __name__ == "__main__":
    unittest.main()
