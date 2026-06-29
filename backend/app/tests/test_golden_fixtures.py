"""CP5 — permanent OFFLINE regression net over every adapter (SPEC_IMPLEMENTATION_CHECKPOINTS §5).

Builds the deterministic trace-preserving narration (the offline floor that ships when the LLM is
unavailable) for each core algorithm and asserts the quality + correctness gates, so the multi-stage
refactor — or any change — can NOT silently regress Prim/Kruskal/BFS/DFS/merge-sort/binary-search/Dijkstra.
Deterministic (seeded) and LLM-free.

Note on coding: the offline floor legitimately has no per-line code anchor (the LLM supplies that), so the
coding cases allow ONLY the "no code anchor" M6 note and require everything else clean.
"""
import unittest

from app.services.examples import generation_report as gr
from app.services.examples import trace_pipeline as tp
from app.services.examples.content_shape import worked_example_shape_violations

# (title that routes to the adapter, expected slug, coding?)
_FIXTURES = [
    ("Understanding Binary Search", "binary_search", False),
    ("Understanding Kruskal's Algorithm", "kruskal", False),
    ("Implementing Kruskal's Algorithm", "kruskal", True),
    ("Understanding Prim's Algorithm", "prim", False),
    ("Implementing Prim's Algorithm", "prim", True),
    ("Understanding Merge Sort", "merge_sort", False),
    ("Breadth-First Search Traversal", "bfs", False),
    ("Depth-First Search Traversal", "dfs_iter", False),
    ("Evaluate the Expression (order of operations)", "arithmetic_eval", False),
    ("Dijkstra's Shortest Path", "dijkstra", False),
]


def _mark_steps(cards):
    for c in cards:
        c["blueprint_key"] = "worked_example"
        c.setdefault("metadata", {}).setdefault("example", {})["role"] = "step"
    return cards


class GoldenFixtures(unittest.TestCase):
    def _check(self, title, slug, coding):
        topic = {"title": title, "topic_type": "coding_implementation" if coding else "algorithm_walkthrough"}
        adapter = tp.route_adapter(topic)
        self.assertIsNotNone(adapter, f"{title}: did not route")
        self.assertEqual(adapter.slug, slug, title)
        trace = tp.select_instance(adapter, tp._seed_for(topic))
        self.assertIsNotNone(trace, f"{title}: no teaching trace")
        self.assertIsNotNone(trace.final_answer, f"{title}: no final answer")

        cards = _mark_steps(tp._deterministic_narration(trace))     # offline floor, trace-preserving
        self.assertEqual(len(cards), len(trace.steps), f"{title}: not 1:1 with steps")

        # content shape: clean, except coding's known no-code-anchor floor limitation
        issues = worked_example_shape_violations(cards, coding=coding)
        if coding:
            issues = [i for i in issues if "code anchor" not in i]
        self.assertEqual(issues, [], f"{title}: M6 issues {issues}")

        # coverage + terminal + the §1.2/CP6 invariant all clean
        cov = tp._coverage_fields(trace, cards)
        self.assertEqual(cov["missing_required_transition_ids"], [], f"{title}: missing required transition")
        self.assertTrue(cov["terminal_rendered"], f"{title}: terminal/completion not rendered")
        rep = {"worked_example": {"adapter": slug, "final_source": "trace_pipeline", "tp_shipped": True,
                                  "verification_level": "trace_verified", **cov}}
        self.assertEqual(gr.invariant_violations(rep), [], f"{title}: invariant violation")

        # no raw machine-state dict ever leaks into a learner-facing result
        self.assertFalse(any(str(c["result"]).lstrip().startswith("{") for c in cards),
                         f"{title}: raw dict in result")

    def test_every_core_adapter_has_a_clean_golden_floor(self):
        for title, slug, coding in _FIXTURES:
            with self.subTest(adapter=slug, title=title):
                self._check(title, slug, coding)


if __name__ == "__main__":
    unittest.main()
