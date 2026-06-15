"""Example blueprint metadata: per-card role/index/total + skipped/unfinished flags.

Each worked-example card is stamped with its blueprint role and step position; an
example_status on the setup card flags when steps were SKIPPED (too few) or the example did
NOT FINISH (final answer never reached). Deterministic, no LLM.

Run: python -m unittest app.tests.test_example_blueprint
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.example_blueprint import MIN_STEPS, stamp_example_metadata


def _cards(n_steps: int, *, setup: bool = True, final_answer_in_last: bool = True, stamp_final: bool = True):
    cards = []
    if setup:
        cards.append({"blueprint_key": "worked_example", "points": ["Problem:", "  - Sort [5, 2, 8]."],
                      "metadata": {"worked_example_setup": True}})
    for i in range(n_steps):
        last = i == n_steps - 1
        pts = ["Now:", "  - state"]
        if last and final_answer_in_last:
            pts.append("Final answer: [2, 5, 8]")
        meta = {}
        if last and stamp_final:
            meta["reaches_final_answer"] = True
        cards.append({"blueprint_key": "worked_example", "points": pts, "metadata": meta})
    return cards


class TestBlueprintMetadata(unittest.TestCase):
    def test_complete_example(self):
        cards = _cards(MIN_STEPS)
        status = stamp_example_metadata(cards, final_answer="[2, 5, 8]")
        self.assertTrue(status["complete"])
        self.assertTrue(status["finished"])
        self.assertFalse(status["skipped"])
        # step cards carry index/total
        steps = [c for c in cards if not (c.get("metadata") or {}).get("worked_example_setup")]
        self.assertEqual([c["metadata"]["example"]["index"] for c in steps], list(range(1, MIN_STEPS + 1)))
        self.assertTrue(all(c["metadata"]["example"]["total"] == MIN_STEPS for c in steps))
        # status lives on the setup card
        setup = cards[0]
        self.assertEqual(setup["metadata"]["example_status"]["reason"], "")

    def test_too_few_steps_flags_skipped(self):
        cards = _cards(2)  # split -> done
        status = stamp_example_metadata(cards, final_answer="[2, 5, 8]")
        self.assertTrue(status["skipped"])
        self.assertFalse(status["complete"])
        self.assertEqual(status["reason"], "steps_skipped")

    def test_does_not_finish_flags_unfinished(self):
        cards = _cards(MIN_STEPS, final_answer_in_last=False, stamp_final=False)
        status = stamp_example_metadata(cards, final_answer="[2, 5, 8]")
        self.assertFalse(status["finished"])
        self.assertEqual(status["reason"], "did_not_finish")

    def test_missing_setup_flagged(self):
        cards = _cards(MIN_STEPS, setup=False)
        status = stamp_example_metadata(cards, final_answer="[2, 5, 8]")
        self.assertFalse(status["has_setup"])
        self.assertEqual(status["reason"], "missing_setup")

    def test_boundary_short_example_allowed(self):
        cards = _cards(2)
        status = stamp_example_metadata(cards, final_answer="[2, 5, 8]", boundary=True)
        self.assertFalse(status["skipped"])
        self.assertTrue(status["complete"])


if __name__ == "__main__":
    unittest.main()
