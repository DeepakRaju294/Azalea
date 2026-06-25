"""Tests for the trace-not-walkthrough gate (#5) and the MST weight differential (C)."""
import unittest

from app.services.gen_foundation.trace_quality import walkthrough_mode_violations
from app.services.gen_foundation.property_checks import check_mst_claimed


class WalkthroughGateTests(unittest.TestCase):
    def test_def_definition_step_flagged(self):
        cards = [{"work": ["def find(parent, vertex): // define find", "return parent[vertex]"],
                  "result": "find function ready for use."}]
        viol = walkthrough_mode_violations(cards)
        self.assertTrue(any("DEFINES a function" in v for v in viol))

    def test_ready_for_use_result_flagged(self):
        cards = [{"work": ["set up the union helper"], "result": "union function ready for combining components."}]
        self.assertTrue(walkthrough_mode_violations(cards))

    def test_real_trace_passes(self):
        cards = [{"work": ["uf.find('A') // root of A is A", "uf.union('A','B') // merge A and B"],
                  "result": "Edge (A, B, 4) added to the MST."}]
        self.assertEqual(walkthrough_mode_violations(cards), [])

    def test_class_definition_also_flagged(self):
        self.assertTrue(walkthrough_mode_violations([{"work": ["class UnionFind: // define"], "result": "r"}]))


class DifferentialTests(unittest.TestCase):
    INPUT = {"nodes": ["A", "B", "C", "D"],
             "edges": [["A", "B", 1], ["B", "C", 2], ["C", "D", 3], ["A", "D", 10], ["B", "D", 1]]}

    def test_non_minimal_mst_flagged(self):
        # connected, 3 edges (V-1), but weight 6 — the true minimum is 4
        viol = check_mst_claimed(self.INPUT, "MST: [(A,B,1),(B,C,2),(C,D,3)]")
        self.assertTrue(any("not minimal" in v and "weighs 4" in v for v in viol))

    def test_minimal_mst_passes(self):
        self.assertEqual(check_mst_claimed(self.INPUT, "MST: [(A,B,1),(B,D,1),(B,C,2)]"), [])

    def test_no_input_edges_skips_differential(self):
        # only structural checks when the input has no weighted edges to build a reference from
        self.assertEqual(check_mst_claimed({"nodes": ["A", "B", "C", "D"]},
                                           "MST: [(A,B,1),(B,D,1),(B,C,2)]"), [])


class ReferenceBackedTests(unittest.TestCase):
    def test_parse_graph_from_problem_text(self):
        from app.services.gen_foundation.property_checks import parse_weighted_graph_from_text
        g = parse_weighted_graph_from_text(
            "Find the MST of the graph with nodes ['A', 'B', 'C'] and edges [['A','B',5],['B','C',2]]")
        self.assertEqual(set(g["nodes"]), {"A", "B", "C"})
        self.assertEqual(g["edges"], [["A", "B", 5.0], ["B", "C", 2.0]])

    def _we(self, problem, final):
        from app.services.gen_foundation.trace_quality import worked_example_correctness_violations
        cards = [{"points": [problem]}, {"points": [final]}]
        return worked_example_correctness_violations(
            cards, {"title": "Kruskal's Algorithm", "topic_type": "algorithm_walkthrough"})

    def test_vague_walkthrough_final_flagged(self):
        viol = self._we("nodes [A,B,C,D,E,F] and edges [[A,B,1],[B,C,2]]",
                        "Final MST edges collection")  # 0 edges stated for 6 nodes
        self.assertTrue(any("V-1=5" in v for v in viol))

    def test_truncated_mst_flagged(self):
        viol = self._we("nodes [A,B,C,D,E,F] and edges [[A,B,1]]",
                        "MST: [(A,B,1),(B,C,2),(C,D,3)]")  # 3 edges < 5
        self.assertTrue(viol)

    def test_correct_complete_mst_passes(self):
        prob = "nodes [A,B,C,D] and edges [[A,B,1],[B,C,2],[C,D,3],[A,D,9]]"
        viol = self._we(prob, "MST: [(A,B,1),(B,C,2),(C,D,3)]")  # 3 edges = V-1, minimal
        self.assertEqual(viol, [])


if __name__ == "__main__":
    unittest.main()
