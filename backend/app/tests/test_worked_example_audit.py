"""Post-generation worked-example completion audit (prose-path INV-COMPLETE).

A worked example that doesn't reach the final answer is regenerated up to a hard cap;
if still incomplete after the cap, it's logged + counted, never silently shipped.
Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_worked_example_audit
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.worked_example_audit import audit_worked_examples
from app.services.visual_v2.invariant_metrics import GLOBAL as INV

_TOPIC = {"id": "t", "title": "DFS", "topic_type": "algorithm_walkthrough"}


def _lesson(we_cards):
    return {"lesson_cards": [{"id": "bg", "blueprint_key": "background"}, *we_cards,
                             {"id": "p", "blueprint_key": "practice"}], "visual_models": []}


def _we(title, points, **meta):
    card = {"id": title, "blueprint_key": "worked_example", "title": title, "points": points}
    if meta:
        card["metadata"] = meta
    return card


class TestAudit(unittest.TestCase):
    def setUp(self):
        INV.reset()

    def test_complete_by_metadata_no_action(self):
        lesson = _lesson([_we("Step 1", ["Start."]), _we("Step 2", ["Visit A."], reaches_final_answer=True)])
        out = audit_worked_examples(lesson, _TOPIC, regenerate=lambda *_: self.fail("should not regen"))
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["regenerations"], 0)

    def test_complete_by_concluding_phrase(self):
        lesson = _lesson([_we("Step 1", ["Start at A."]),
                          _we("Done", ["The final traversal order is A, B, C."])])
        self.assertEqual(audit_worked_examples(lesson, _TOPIC)["status"], "complete")

    def test_regeneration_fixes_it(self):
        lesson = _lesson([_we("Step 1", ["Start at A."])])  # cut short, no conclusion

        def regen(lj, topic):
            # the "LLM" appends a concluding card on the first retry
            lj["lesson_cards"].insert(-1, _we("Final", ["The answer is A, B, C."]))

        out = audit_worked_examples(lesson, _TOPIC, regenerate=regen, max_regenerations=2)
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["regenerations"], 1)

    def test_hits_cap_then_logs_and_counts(self):
        lesson = _lesson([_we("Step 1", ["Start at A."])])  # never completes
        calls = {"n": 0}

        def regen(lj, topic):
            calls["n"] += 1  # a no-op "LLM" that never fixes it

        out = audit_worked_examples(lesson, _TOPIC, regenerate=regen, max_regenerations=2)
        self.assertEqual(out["status"], "incomplete_after_cap")
        self.assertEqual(out["regenerations"], 2)      # exactly the cap, no more
        self.assertEqual(calls["n"], 2)                # regenerated exactly twice
        self.assertEqual(INV.snapshot()["fallbacks"].get("incomplete_worked_example"), 1)
        self.assertEqual(INV.snapshot()["worked_example_regens"].get("2"), 1)

    def test_no_regenerator_logs_immediately(self):
        lesson = _lesson([_we("Step 1", ["Start at A."])])
        out = audit_worked_examples(lesson, _TOPIC, regenerate=None, max_regenerations=2)
        self.assertEqual(out["status"], "incomplete_after_cap")
        self.assertEqual(out["regenerations"], 0)
        self.assertEqual(INV.snapshot()["fallbacks"].get("incomplete_worked_example"), 1)


if __name__ == "__main__":
    unittest.main()
