"""Example blueprint validation: transition structure + completeness + coverage flags.

Each step carries a full transition (prior/decision/action/resulting) and cases_covered; the
blueprint validates structure (no missing/no-op transitions), completeness (enough steps,
reaches the expected final answer), and coverage (required_cases exercised), stamping a nested
example_status. Deterministic, no LLM.

Run: python -m unittest app.tests.test_example_blueprint
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.example_blueprint import DEFAULT_MIN_STEPS, stamp_example_metadata


def _step(prior, action, resulting, *, decision="because", final=False, cases=None):
    meta = {"transition": {"prior_state": prior, "decision": decision, "action": action,
                           "resulting_state": resulting}}
    if final:
        meta["final_answer"] = resulting
    if cases:
        meta["cases_covered"] = cases
    return {"blueprint_key": "worked_example", "points": ["Now:", f"  - {resulting}"], "metadata": meta}


def _cards(n_steps, *, setup=True, no_op_last=False, missing_last=False, cases_on_last=None):
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
            cards.append(_step(f"state {i}", f"act {i}", "[2, 5, 8]" if last else f"state {i + 1}",
                               final=last, cases=cases_on_last if last else None))
    return cards


class TestBlueprintValidation(unittest.TestCase):
    def test_complete_example(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["complete"], status)
        self.assertTrue(status["completeness"]["finished"])
        self.assertFalse(status["completeness"]["skipped"])
        self.assertEqual(status["structure"]["transition_issues"], [])

    def test_too_few_steps_flags_skipped(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["completeness"]["skipped"])
        self.assertEqual(status["reason"], "steps_skipped")

    def test_expected_min_steps_overrides_default(self):
        status = stamp_example_metadata(_cards(6), expected_final_answer="[2, 5, 8]", expected_min_steps=10)
        self.assertTrue(status["completeness"]["skipped"])

    def test_missing_transition_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, missing_last=True), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["structure"]["transition_issues"])
        self.assertEqual(status["reason"], "missing_transition")

    def test_no_op_step_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, no_op_last=True), expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["structure"]["transition_issues"][0]["issue"], "no_op_step")

    def test_decision_required(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[1]["metadata"]["transition"]["decision"] = ""   # drop the decision on one step
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["structure"]["transition_issues"][0]["issue"], "missing_transition")

    def test_does_not_finish(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[-1]["metadata"]["transition"]["resulting_state"] = "still working"
        cards[-1]["metadata"]["final_answer"] = "still working"
        cards[-1]["points"] = ["Now:", "  - still working"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertFalse(status["completeness"]["finished"])
        self.assertEqual(status["reason"], "did_not_finish")

    def test_missing_required_case_flagged(self):
        # required_cases given, but no step tags cases_covered -> coverage fails.
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS), expected_final_answer="[2, 5, 8]",
                                        required_cases=("leftover tail", "base case"))
        self.assertEqual(status["coverage"]["missing_cases"], ["leftover tail", "base case"])
        self.assertEqual(status["reason"], "missing_required_case")

    def test_required_cases_covered(self):
        cards = _cards(DEFAULT_MIN_STEPS, cases_on_last=["leftover tail"])
        cards[1]["metadata"]["cases_covered"] = ["base case"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]",
                                        required_cases=("leftover tail", "base case"))
        self.assertEqual(status["coverage"]["missing_cases"], [])
        self.assertTrue(status["complete"])

    def test_allow_short_example(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]", allow_short_example=True)
        self.assertFalse(status["completeness"]["skipped"])
        self.assertTrue(status["complete"])

    def test_setup_metadata_stamped(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]", expected_min_steps=6,
                               required_cases=("c1",))
        setup = cards[0]["metadata"]
        self.assertEqual(setup["expected_final_answer"], "[2, 5, 8]")
        self.assertEqual(setup["expected_min_steps"], 6)
        self.assertEqual(setup["required_cases"], ["c1"])


if __name__ == "__main__":
    unittest.main()
