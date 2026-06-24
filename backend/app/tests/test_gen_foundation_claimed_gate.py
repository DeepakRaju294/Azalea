"""Tests for the model-only property gate (#1) — invariants on the claimed final answer, no executor."""
import unittest

from app.services.gen_foundation.property_checks import (
    claimed_answer_violations, check_mst_claimed, check_sort_claimed,
)
from app.services.gen_foundation.validators import validate_artifact

EIGHT = {"nodes": ["A", "B", "C", "D", "E", "F", "G", "H"]}


class MstClaimedTests(unittest.TestCase):
    def test_the_real_kruskal_failure(self):
        # the actual broken lesson: 4 edges for an 8-node graph, and disconnected
        claimed = "Final MST consists of edges: [(B, C, 1), (D, E, 13), (E, F, 15), (F, G, 19)]"
        viol = check_mst_claimed(EIGHT, claimed)
        self.assertTrue(any("V-1=7" in v for v in viol))           # wrong edge count
        self.assertTrue(any("disconnected" in v for v in viol))    # A, H, and {B,C} never joined

    def test_prims_two_edge_result(self):
        viol = check_mst_claimed(EIGHT, "The MST edges are: [(0, 'A'), (3, 'B')]")
        self.assertTrue(viol)  # 1 parseable edge on 8 nodes

    def test_correct_seven_edge_mst_passes(self):
        good = "MST: [(B,C,1),(D,E,13),(C,D,14),(E,F,15),(F,G,19),(A,B,29),(G,H,37)]"
        self.assertEqual(check_mst_claimed(EIGHT, good), [])

    def test_unparseable_answer_no_false_fail(self):
        self.assertEqual(check_mst_claimed(EIGHT, "the minimum spanning tree is now complete"), [])


class SortClaimedTests(unittest.TestCase):
    def test_wrong_length_flagged(self):
        viol = check_sort_claimed([5, 3, 8, 1, 9, 2], "sorted: [1, 2, 3, 5]")
        self.assertTrue(any("not a permutation" in v for v in viol))

    def test_correct_length_passes(self):
        self.assertEqual(check_sort_claimed([5, 3, 8, 1], "sorted: [1, 3, 5, 8]"), [])


class GateWiringTests(unittest.TestCase):
    def _artifact(self, final_answer, cards):
        return {
            "category": "coding_implementation",
            "topic_family": "graph_mst_kruskal",
            "example_input": EIGHT,
            "cards": cards,
            "final_answer": final_answer,
            "step_ids": [f"step_{i+1}" for i in range(len(cards))],
            "projection_coverage": {"required_cases": {},
                                    "teaching_step_reaching_final": f"step_{len(cards)}"},
            "confidence_meta": {"trace_mode": "model_only", "trace_confidence": "low",
                                "trace_validation_status": "unavailable"},
        }

    def test_validate_artifact_rejects_truncated_mst(self):
        claimed = "Final MST consists of edges: [(B, C, 1), (D, E, 13), (E, F, 15), (F, G, 19)]"
        card = {"title": "t", "goal": "g", "reasoning": "r", "work": [claimed], "result": claimed,
                "state_relevance": "none", "state_delta": None, "cases_covered": []}
        errors = validate_artifact(self._artifact(claimed, [card]))
        self.assertTrue(any("mst" in e for e in errors), errors)

    def test_validate_artifact_accepts_correct_mst(self):
        good = "MST edges: [(B,C,1),(D,E,13),(C,D,14),(E,F,15),(F,G,19),(A,B,29),(G,H,37)]"
        card = {"title": "t", "goal": "g", "reasoning": "r", "work": [good], "result": good,
                "state_relevance": "none", "state_delta": None, "cases_covered": []}
        errors = validate_artifact(self._artifact(good, [card]))
        self.assertFalse(any("mst" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
