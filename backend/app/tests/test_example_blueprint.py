"""Example blueprint validation: transition structure + skipped/unfinished flags.

Each worked-example step carries a transition (prior/action/resulting); the blueprint validates
the structure (no missing/no-op transitions) and completeness (enough steps, reaches the
expected final answer) and stamps an example_status. Deterministic, no LLM.

Run: python -m unittest app.tests.test_example_blueprint
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.example_blueprint import DEFAULT_MIN_STEPS, stamp_example_metadata


def _step(prior: str, action: str, resulting: str, *, final: bool = False) -> dict:
    meta = {"transition": {"prior_state": prior, "action": action, "resulting_state": resulting}}
    if final:
        meta["reaches_final_answer"] = True
    return {"blueprint_key": "worked_example", "points": ["Now:", f"  - {resulting}"], "metadata": meta}


def _cards(n_steps: int, *, setup: bool = True, no_op_last: bool = False, missing_last: bool = False):
    cards = []
    if setup:
        cards.append({"blueprint_key": "worked_example", "points": ["Problem:", "  - Sort [5, 2, 8]."],
                      "metadata": {"worked_example_setup": True}})
    for i in range(n_steps):
        last = i == n_steps - 1
        if last and missing_last:
            cards.append({"blueprint_key": "worked_example", "points": ["...vague..."], "metadata": {"transition": {}}})
        elif last and no_op_last:
            cards.append(_step(f"state {i}", "do nothing", f"state {i}"))  # prior == resulting
        else:
            cards.append(_step(f"state {i}", f"act {i}", "[2, 5, 8]" if last else f"state {i + 1}", final=last))
    return cards


class TestBlueprintValidation(unittest.TestCase):
    def test_complete_example(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["complete"], status)
        self.assertTrue(status["finished"])
        self.assertFalse(status["skipped"])
        self.assertEqual(status["transition_issues"], [])
        steps = [c for c in cards if not (c.get("metadata") or {}).get("worked_example_setup")]
        self.assertEqual([c["metadata"]["example"]["index"] for c in steps], list(range(1, DEFAULT_MIN_STEPS + 1)))

    def test_too_few_steps_flags_skipped(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["skipped"])
        self.assertEqual(status["reason"], "steps_skipped")

    def test_expected_steps_overrides_default(self):
        # 6 steps is fine by the default, but if the topic expects 10, it's short.
        status = stamp_example_metadata(_cards(6), expected_final_answer="[2, 5, 8]", expected_steps=10)
        self.assertTrue(status["skipped"])

    def test_missing_transition_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, missing_last=True), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["transition_issues"])
        self.assertEqual(status["reason"], "missing_transition")

    def test_no_op_step_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, no_op_last=True), expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["transition_issues"][0]["issue"], "no_op_step")

    def test_does_not_finish(self):
        # Last step's resulting state isn't the expected answer and isn't stamped final.
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[-1]["metadata"].pop("reaches_final_answer", None)
        cards[-1]["metadata"]["transition"]["resulting_state"] = "still working"
        cards[-1]["points"] = ["Now:", "  - still working"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertFalse(status["finished"])
        self.assertEqual(status["reason"], "did_not_finish")

    def test_allow_short_example(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]", allow_short_example=True)
        self.assertFalse(status["skipped"])
        self.assertTrue(status["complete"])


if __name__ == "__main__":
    unittest.main()
