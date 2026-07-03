"""A concept-category topic (concept_intuition / definition / formula / proof / comparison) must NOT ship an
over-cap algorithm LINE-TRACE as its 'worked example'. A concept example is a short conceptual illustration
(the idea applied once), never a multi-step execution. When an over-cap example cannot be bounded, it is
WITHHELD. (Regression for the "Concept of Comparison-Based Sorting" topic that shipped an 18-card line-trace.)
Offline: with a dummy key the bounded re-solve is unavailable, which is exactly the path that used to keep
the over-cap trace."""
import unittest

from app.services.examples.solver import _enforce_worked_example_schema_cap


def _oversized_sol(n=18):
    return {"problem": "p", "expected_final_answer": "done",
            "cards": [{"work": [f"compare arr[{i}] with arr[{i+1}]"], "result": f"step {i}"} for i in range(n)]}


class ConceptExampleWithhold(unittest.TestCase):
    def test_concept_over_cap_line_trace_is_withheld(self):
        sol = _oversized_sol(18)
        topic = {"id": "t1", "topic_type": "concept_intuition", "title": "Concept of Comparison-Based Sorting"}
        out, bounded = _enforce_worked_example_schema_cap(sol, topic, code=None)
        self.assertEqual(out.get("cards"), [], "over-cap concept example should be withheld (no cards)")
        self.assertFalse(bounded)

    def test_definition_and_proof_topics_also_withheld(self):
        for tt in ("definition", "proof", "comparison", "formula"):
            sol = _oversized_sol(20)
            out, _ = _enforce_worked_example_schema_cap(sol, {"id": "x", "topic_type": tt, "title": tt}, code=None)
            with self.subTest(topic_type=tt):
                self.assertEqual(out.get("cards"), [])

    def test_within_cap_concept_example_is_kept(self):
        sol = _oversized_sol(4)   # under the simple_concept cap (7)
        out, bounded = _enforce_worked_example_schema_cap(
            sol, {"id": "t2", "topic_type": "concept_intuition", "title": "c"}, code=None)
        self.assertEqual(len(out.get("cards")), 4)   # short concept example is fine — kept
        self.assertFalse(bounded)

    def test_coding_topic_is_not_withheld(self):
        # a coding topic over-cap is handled by the existing re-solve/flag path, NOT the concept withhold
        sol = _oversized_sol(20)
        out, _ = _enforce_worked_example_schema_cap(
            sol, {"id": "t3", "topic_type": "coding_implementation", "title": "Merge Sort"}, code="def f(): pass")
        self.assertNotEqual(out.get("cards"), [], "coding topic must not be silently withheld")


if __name__ == "__main__":
    unittest.main()
